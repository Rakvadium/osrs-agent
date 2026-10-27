package com.osrsagent;

import com.google.gson.Gson;
import java.io.IOException;
import java.io.Reader;
import java.nio.file.StandardCopyOption;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import javax.inject.Inject;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Client;
import net.runelite.api.GameState;
import net.runelite.api.ItemContainer;
import net.runelite.api.Player;
import net.runelite.api.events.GameStateChanged;
import net.runelite.api.events.GameTick;
import net.runelite.api.events.ItemContainerChanged;
import net.runelite.api.events.StatChanged;
import net.runelite.api.gameval.VarPlayerID;
import net.runelite.client.eventbus.Subscribe;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;
import net.runelite.client.util.Filepath;

/**
 * Writes plugin-data/osrs-agent/snapshots/&lt;rsn&gt;.json whenever the account
 * state changes, for the planning skills in this repo to read.
 */
@Slf4j
@PluginDescriptor(
	name = "OSRS Agent Snapshot",
	description = "Exports account state to a local JSON file for planning tools",
	tags = {"export", "bank", "json"},
	internalName = "osrs-agent"
)
public class OsrsAgentPlugin extends Plugin
{
	/** Coalesces bursts of changes (e.g. withdrawing a loadout) into one write. */
	private static final int WRITE_DEBOUNCE_TICKS = 3;
	/** Quest states run a client script each, so they are refreshed sparingly. */
	private static final int QUEST_REFRESH_TICKS = 100;
	/** Captures varbit-only changes (diaries, rune pouch) that fire no event we track. */
	private static final int HEARTBEAT_TICKS = 100;

	@Inject
	private Client client;

	@Inject
	private SnapshotBuilder builder;

	@Inject
	private Gson baseGson;

	private Gson gson;
	private ExecutorService writer;

	private final Map<String, Snapshot.Container> containers = new ConcurrentHashMap<>();
	private Map<String, String> quests;
	private volatile String rsn;
	/** Writes wait for the previous snapshot to be read back, so the bank is never dropped. */
	private volatile boolean restored;
	private int tick;
	private int lastWriteTick;
	private int lastQuestTick;
	private int lastQuestPoints;
	private boolean dirty;

	@Override
	protected void startUp()
	{
		gson = baseGson.newBuilder().setPrettyPrinting().create();
		writer = Executors.newSingleThreadExecutor();
		reset();
	}

	@Override
	protected void shutDown()
	{
		writer.shutdownNow();
		reset();
	}

	@Subscribe
	public void onGameStateChanged(GameStateChanged event)
	{
		if (event.getGameState() == GameState.LOGIN_SCREEN)
		{
			reset();
		}
	}

	@Subscribe
	public void onItemContainerChanged(ItemContainerChanged event)
	{
		TrackedContainer.byId(event.getContainerId())
			.ifPresent(tracked -> capture(tracked, event.getItemContainer()));
	}

	@Subscribe
	public void onStatChanged(StatChanged event)
	{
		dirty = true;
	}

	@Subscribe
	public void onGameTick(GameTick event)
	{
		tick++;
		if (rsn == null && !identifyPlayer())
		{
			return;
		}

		int questPoints = client.getVarpValue(VarPlayerID.QP);
		if (quests == null || questPoints != lastQuestPoints || tick - lastQuestTick >= QUEST_REFRESH_TICKS)
		{
			Map<String, String> fresh = builder.buildQuests();
			dirty |= !fresh.equals(quests);
			quests = fresh;
			lastQuestPoints = questPoints;
			lastQuestTick = tick;
		}

		if (tick - lastWriteTick >= HEARTBEAT_TICKS)
		{
			dirty = true;
		}

		if (dirty && restored && tick - lastWriteTick >= WRITE_DEBOUNCE_TICKS)
		{
			dirty = false;
			lastWriteTick = tick;
			Snapshot snapshot = builder.build(rsn, quests, containers);
			writer.submit(() -> write(snapshot));
		}
	}

	private boolean identifyPlayer()
	{
		Player player = client.getLocalPlayer();
		if (client.getGameState() != GameState.LOGGED_IN || player == null || player.getName() == null)
		{
			return false;
		}

		rsn = player.getName().replace('\u00A0', ' ');
		for (TrackedContainer tracked : TrackedContainer.values())
		{
			ItemContainer container = client.getItemContainer(tracked.id);
			if (container != null)
			{
				capture(tracked, container);
			}
		}
		String name = rsn;
		writer.submit(() -> restoreContainers(name));
		return true;
	}

	private void capture(TrackedContainer tracked, ItemContainer container)
	{
		containers.put(tracked.key, builder.buildContainer(tracked, container));
		dirty = true;
	}

	/**
	 * Reloads containers from the previous snapshot so the bank and other
	 * open-to-see storage survive restarts. Anything captured this session wins.
	 */
	private void restoreContainers(String name)
	{
		try
		{
			Filepath file = snapshotFile(name);
			if (file.exists())
			{
				try (Reader reader = file.openReader())
				{
					Snapshot previous = gson.fromJson(reader, Snapshot.class);
					if (previous != null && previous.containers != null && name.equals(previous.rsn) && name.equals(rsn))
					{
						previous.containers.forEach(containers::putIfAbsent);
					}
				}
			}
		}
		catch (IOException | RuntimeException e)
		{
			log.warn("Could not restore previous snapshot for {}", name, e);
		}
		if (name.equals(rsn))
		{
			restored = true;
		}
	}

	private void write(Snapshot snapshot)
	{
		try
		{
			Filepath file = snapshotFile(snapshot.rsn);
			Filepath tmp = file.getParent().joinSegment(file.getFileName() + ".tmp");
			tmp.write(gson.toJson(snapshot));
			tmp.moveTo(file, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
			log.debug("Wrote snapshot {}", file);
		}
		catch (IOException e)
		{
			log.warn("Could not write snapshot for {}", snapshot.rsn, e);
		}
	}

	private Filepath snapshotFile(String name) throws IOException
	{
		Filepath dir = getPluginDirectory().joinSegment("snapshots");
		dir.createDirectories();
		return dir.joinSegment(name.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]+", "_") + ".json");
	}

	private void reset()
	{
		rsn = null;
		restored = false;
		quests = null;
		containers.clear();
		dirty = false;
		lastWriteTick = tick;
	}
}

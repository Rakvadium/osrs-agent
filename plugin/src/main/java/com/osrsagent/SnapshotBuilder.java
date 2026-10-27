package com.osrsagent;

import java.time.Instant;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.stream.IntStream;
import javax.inject.Inject;
import javax.inject.Singleton;
import net.runelite.api.Client;
import net.runelite.api.EnumComposition;
import net.runelite.api.EnumID;
import net.runelite.api.EquipmentInventorySlot;
import net.runelite.api.ItemComposition;
import net.runelite.api.ItemContainer;
import net.runelite.api.Player;
import net.runelite.api.Quest;
import net.runelite.api.Skill;
import net.runelite.api.coords.WorldPoint;
import net.runelite.api.gameval.VarPlayerID;
import net.runelite.api.gameval.VarbitID;
import net.runelite.client.game.ItemManager;

/**
 * Reads game state into {@link Snapshot} objects. Every method must run on the
 * client thread.
 */
@Singleton
class SnapshotBuilder
{
	private static final int[] RUNE_POUCH_TYPES = {
		VarbitID.RUNE_POUCH_TYPE_1, VarbitID.RUNE_POUCH_TYPE_2, VarbitID.RUNE_POUCH_TYPE_3,
		VarbitID.RUNE_POUCH_TYPE_4, VarbitID.RUNE_POUCH_TYPE_5, VarbitID.RUNE_POUCH_TYPE_6,
	};
	private static final int[] RUNE_POUCH_QUANTITIES = {
		VarbitID.RUNE_POUCH_QUANTITY_1, VarbitID.RUNE_POUCH_QUANTITY_2, VarbitID.RUNE_POUCH_QUANTITY_3,
		VarbitID.RUNE_POUCH_QUANTITY_4, VarbitID.RUNE_POUCH_QUANTITY_5, VarbitID.RUNE_POUCH_QUANTITY_6,
	};
	private static final int NOTED_TEMPLATE = 799;

	@Inject
	private Client client;

	@Inject
	private ItemManager itemManager;

	/**
	 * Builds the always-available parts of the snapshot. Quests and containers
	 * are supplied by the caller because they are cached between builds.
	 */
	Snapshot build(String rsn, Map<String, String> quests, Map<String, Snapshot.Container> containers)
	{
		Snapshot s = new Snapshot();
		s.rsn = rsn;
		s.accountType = accountType(client.getVarbitValue(VarbitID.IRONMAN));
		s.capturedAt = Instant.now().toString();
		s.world = client.getWorld();
		s.worldTypes = client.getWorldType().stream().map(Enum::name).collect(Collectors.toList());
		s.totalLevel = client.getTotalLevel();
		s.questPoints = client.getVarpValue(VarPlayerID.QP);
		s.quests = quests;
		s.containers = new LinkedHashMap<>(containers);

		Player player = client.getLocalPlayer();
		if (player != null)
		{
			s.combatLevel = player.getCombatLevel();
			WorldPoint wp = WorldPoint.fromLocalInstance(client, player.getLocalLocation());
			Snapshot.Location loc = new Snapshot.Location();
			loc.x = wp.getX();
			loc.y = wp.getY();
			loc.plane = wp.getPlane();
			loc.regionId = wp.getRegionID();
			s.location = loc;
		}

		for (Skill skill : Skill.values())
		{
			// OVERALL is a deprecated pseudo-skill; totalLevel covers it.
			if ("Overall".equals(skill.getName()))
			{
				continue;
			}
			Snapshot.SkillState state = new Snapshot.SkillState();
			state.level = client.getRealSkillLevel(skill);
			state.boostedLevel = client.getBoostedSkillLevel(skill);
			state.xp = client.getSkillExperience(skill);
			s.skills.put(skill.getName().toLowerCase(Locale.ROOT), state);
		}

		for (Diary diary : Diary.values())
		{
			Map<String, Snapshot.DiaryTier> tiers = new LinkedHashMap<>();
			int[] varbits = diary.varbits();
			for (int i = 0; i < varbits.length; i++)
			{
				Snapshot.DiaryTier tier = new Snapshot.DiaryTier();
				tier.rawValue = client.getVarbitValue(varbits[i]);
				tier.complete = tier.rawValue > 0;
				tiers.put(Diary.TIERS[i], tier);
			}
			s.diaries.put(diary.key, tiers);
		}

		s.runePouch = buildRunePouch();
		return s;
	}

	Map<String, String> buildQuests()
	{
		Map<String, String> quests = new LinkedHashMap<>();
		for (Quest quest : Quest.values())
		{
			quests.put(quest.getName(), quest.getState(client).name());
		}
		return quests;
	}

	Snapshot.Container buildContainer(TrackedContainer tracked, ItemContainer container)
	{
		Snapshot.Container out = new Snapshot.Container();
		out.capturedAt = Instant.now().toString();
		out.capacity = tracked.capacity;

		net.runelite.api.Item[] items = container.getItems();
		int used = 0;
		for (int slot = 0; slot < items.length; slot++)
		{
			net.runelite.api.Item item = items[slot];
			if (item.getId() < 0 || item.getQuantity() <= 0)
			{
				continue;
			}
			ItemComposition comp = itemManager.getItemComposition(item.getId());
			if (comp.getPlaceholderTemplateId() != -1)
			{
				continue;
			}
			used++;
			boolean noted = comp.getNote() == NOTED_TEMPLATE;
			int id = noted ? comp.getLinkedNoteId() : item.getId();
			out.items.add(item(id, noted ? itemManager.getItemComposition(id).getName() : comp.getName(),
				item.getQuantity(), noted, slotName(tracked, slot)));
		}

		if (tracked.capacity != null)
		{
			out.freeSlots = tracked.capacity - used;
		}
		return out;
	}

	private List<Snapshot.Item> buildRunePouch()
	{
		EnumComposition runeEnum = client.getEnum(EnumID.RUNEPOUCH_RUNE);
		return IntStream.range(0, RUNE_POUCH_TYPES.length)
			.filter(i -> client.getVarbitValue(RUNE_POUCH_TYPES[i]) > 0 && client.getVarbitValue(RUNE_POUCH_QUANTITIES[i]) > 0)
			.mapToObj(i ->
			{
				int id = runeEnum.getIntValue(client.getVarbitValue(RUNE_POUCH_TYPES[i]));
				return item(id, itemManager.getItemComposition(id).getName(),
					client.getVarbitValue(RUNE_POUCH_QUANTITIES[i]), false, null);
			})
			.collect(Collectors.toList());
	}

	private static String accountType(int ironmanVarbit)
	{
		switch (ironmanVarbit)
		{
			case 0:
				return "NORMAL";
			case 1:
				return "IRONMAN";
			case 2:
				return "ULTIMATE_IRONMAN";
			case 3:
				return "HARDCORE_IRONMAN";
			case 4:
				return "GROUP_IRONMAN";
			case 5:
				return "HARDCORE_GROUP_IRONMAN";
			case 6:
				return "UNRANKED_GROUP_IRONMAN";
			default:
				return "UNKNOWN_" + ironmanVarbit;
		}
	}

	private static String slotName(TrackedContainer tracked, int slot)
	{
		if (tracked == TrackedContainer.EQUIPMENT)
		{
			return Arrays.stream(EquipmentInventorySlot.values())
				.filter(s -> s.getSlotIdx() == slot)
				.map(Enum::name)
				.findFirst()
				.orElse(String.valueOf(slot));
		}
		return tracked == TrackedContainer.INVENTORY ? String.valueOf(slot) : null;
	}

	private static Snapshot.Item item(int id, String name, int quantity, boolean noted, String slot)
	{
		Snapshot.Item item = new Snapshot.Item();
		item.id = id;
		item.name = name;
		item.quantity = quantity;
		item.noted = noted;
		item.slot = slot;
		return item;
	}
}

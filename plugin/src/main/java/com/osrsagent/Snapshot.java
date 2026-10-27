package com.osrsagent;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The JSON document written per character. Field names are the on-disk schema
 * read by the planning skills, so treat renames as breaking changes and bump
 * {@link #SCHEMA_VERSION}.
 */
class Snapshot
{
	static final int SCHEMA_VERSION = 1;

	int schemaVersion = SCHEMA_VERSION;
	String rsn;
	String accountType;
	String capturedAt;
	int world;
	List<String> worldTypes = new ArrayList<>();
	Location location;
	int combatLevel;
	int totalLevel;
	int questPoints;
	Map<String, SkillState> skills = new LinkedHashMap<>();
	Map<String, String> quests = new LinkedHashMap<>();
	Map<String, Map<String, DiaryTier>> diaries = new LinkedHashMap<>();
	List<Item> runePouch = new ArrayList<>();
	/**
	 * Keyed by {@link TrackedContainer#key}. Containers only visible while open
	 * (bank, seed vault, ...) keep their last captured state, so check
	 * {@link Container#capturedAt} before trusting them. A missing key means the
	 * container has never been seen.
	 */
	Map<String, Container> containers = new LinkedHashMap<>();

	static class Location
	{
		int x;
		int y;
		int plane;
		int regionId;
	}

	static class SkillState
	{
		int level;
		int boostedLevel;
		int xp;
	}

	static class DiaryTier
	{
		boolean complete;
		int rawValue;
	}

	static class Container
	{
		String capturedAt;
		/** Only set for slot-limited containers (inventory: 28). */
		Integer capacity;
		Integer freeSlots;
		List<Item> items = new ArrayList<>();
	}

	static class Item
	{
		/** Unnoted item ID, so noted and unnoted stacks compare equal. */
		int id;
		String name;
		int quantity;
		boolean noted;
		/** Inventory slot index, or equipment slot name (e.g. WEAPON). */
		String slot;
	}
}

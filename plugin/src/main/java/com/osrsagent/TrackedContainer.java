package com.osrsagent;

import java.util.Arrays;
import java.util.Optional;
import lombok.AllArgsConstructor;
import net.runelite.api.gameval.InventoryID;

@AllArgsConstructor
enum TrackedContainer
{
	INVENTORY(InventoryID.INV, "inventory", 28),
	EQUIPMENT(InventoryID.WORN, "equipment", null),
	BANK(InventoryID.BANK, "bank", null),
	SEED_VAULT(InventoryID.SEED_VAULT, "seedVault", null),
	LOOTING_BAG(InventoryID.LOOTING_BAG, "lootingBag", null),
	TACKLE_BOX(InventoryID.TACKLE_BOX, "tackleBox", null),
	GROUP_STORAGE(InventoryID.INV_GROUP_TEMP, "groupStorage", null);

	final int id;
	final String key;
	final Integer capacity;

	static Optional<TrackedContainer> byId(int id)
	{
		return Arrays.stream(values()).filter(c -> c.id == id).findFirst();
	}
}

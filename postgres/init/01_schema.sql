-- 1. WorldSnapshots (親: バックアップの時点)
CREATE TABLE IF NOT EXISTS WorldSnapshots (
    world_snapshot_id SERIAL PRIMARY KEY,
    snapshot_date TIMESTAMP NOT NULL,
    world_name VARCHAR(255)
);

-- 2. Items (独立: アイテムマスタ)
CREATE TABLE IF NOT EXISTS Items (
    item_id VARCHAR(255) PRIMARY KEY,
    item_name_jp VARCHAR(255) NOT NULL,
    item_category VARCHAR(100)
);

-- 3. Chests (子: WorldSnapshotsを参照)
CREATE TABLE IF NOT EXISTS Chests (
    chest_id SERIAL PRIMARY KEY,
    world_snapshot_id INT NOT NULL,
    x_coord INT NOT NULL,
    y_coord INT NOT NULL,
    z_coord INT NOT NULL,
    FOREIGN KEY (world_snapshot_id) REFERENCES WorldSnapshots (world_snapshot_id) ON DELETE CASCADE
);

-- 4. ChestContents (孫: ChestsとItemsを参照)
CREATE TABLE IF NOT EXISTS ChestContents (
    content_id SERIAL PRIMARY KEY,
    chest_id INT NOT NULL,
    item_id VARCHAR(255) NOT NULL,
    quantity INT NOT NULL,
    FOREIGN KEY (chest_id) REFERENCES Chests (chest_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES Items (item_id)
);

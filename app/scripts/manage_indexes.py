"""MongoDB index management utilities."""

import asyncio
from typing import Dict, List

from app.core.logging import get_logger
from app.infrastructure.database.mongodb import mongodb

logger = get_logger(__name__)


class IndexManager:
    """Utility class for managing MongoDB indexes."""

    def __init__(self):
        self.db = mongodb.get_database()

    async def list_all_indexes(self) -> Dict[str, List[Dict]]:
        """List all indexes across collections."""
        collections = await self.db.list_collection_names()
        result = {}

        for collection_name in collections:
            collection = self.db[collection_name]
            indexes = await collection.list_indexes().to_list(None)
            result[collection_name] = [
                {
                    "name": idx.get("name"),
                    "key": idx.get("key", {}),
                    "unique": idx.get("unique", False),
                    "sparse": idx.get("sparse", False),
                }
                for idx in indexes
            ]

        return result

    async def show_collection_stats(self, collection_name: str) -> Dict:
        """Show statistics for a collection."""
        try:
            collection = self.db[collection_name]
            stats = await self.db.command("collStats", collection_name)

            # Get index stats
            indexes = await collection.list_indexes().to_list(None)
            index_info = []
            index_sizes = stats.get("indexSizes", {})

            for idx in indexes:
                if idx.get("name") != "_id_":  # Skip default _id_ index
                    index_info.append(
                        {
                            "name": idx.get("name"),
                            "key": idx.get("key", {}),
                            "size_bytes": index_sizes.get(idx.get("name"), 0),
                        }
                    )

            return {
                "collection": collection_name,
                "document_count": stats.get("count", 0),
                "size_bytes": stats.get("size", 0),
                "storage_size_bytes": stats.get("storageSize", 0),
                "total_index_size_bytes": stats.get("totalIndexSize", 0),
                "indexes": index_info,
            }
        except Exception as e:
            logger.error(f"Failed to get stats for collection {collection_name}: {e}")
            return {"error": str(e)}

    async def drop_deprecated_collection(
        self, collection_name: str, confirm: bool = False
    ) -> bool:
        """Drop a deprecated collection (with safety check)."""
        if not confirm:
            logger.warning(f"Dry run: Would drop collection '{collection_name}'")
            return False

        try:
            collection = self.db[collection_name]
            count = await collection.estimated_document_count()

            if count > 0:
                logger.error(
                    f"Cannot drop collection '{collection_name}' - contains {count} documents"
                )
                return False

            await collection.drop()
            logger.info(f"Successfully dropped empty collection '{collection_name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to drop collection '{collection_name}': {e}")
            return False

    async def create_index_if_not_exists(
        self, collection_name: str, index_spec: List, **kwargs
    ) -> bool:
        """Create index only if it doesn't exist."""
        try:
            collection = self.db[collection_name]
            existing_indexes = await collection.list_indexes().to_list(None)

            # Check if index already exists
            for idx in existing_indexes:
                if idx.get("key") == dict(index_spec):
                    logger.debug(
                        f"Index {index_spec} already exists on {collection_name}"
                    )
                    return True

            # Create the index
            await collection.create_index(index_spec, **kwargs)
            logger.info(f"Created index {index_spec} on {collection_name}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to create index {index_spec} on {collection_name}: {e}"
            )
            return False

    async def explain_query(self, collection_name: str, query: Dict) -> Dict:
        """Get query execution plan for performance analysis."""
        try:
            collection = self.db[collection_name]
            explanation = await collection.find(query).explain()
            return explanation
        except Exception as e:
            logger.error(f"Failed to explain query on {collection_name}: {e}")
            return {"error": str(e)}


async def main():
    """Main function for index management operations."""
    await mongodb.connect()
    manager = IndexManager()

    print("=== MongoDB Index Management ===\n")

    # List all indexes
    print("📊 Current Indexes:")
    indexes = await manager.list_all_indexes()
    for collection, idx_list in indexes.items():
        print(f"\n🗂️  {collection}:")
        for idx in idx_list:
            unique_str = " (UNIQUE)" if idx["unique"] else ""
            sparse_str = " (SPARSE)" if idx["sparse"] else ""
            print(f"   • {idx['name']}: {idx['key']}{unique_str}{sparse_str}")

    # Show collection statistics
    print(f"\n📈 Collection Statistics:")
    for collection in [
        "users",
        "user_messages",
        "bot_messages",
        "workflow_states",
        "messages",
    ]:
        stats = await manager.show_collection_stats(collection)
        if "error" not in stats:
            size_mb = stats["size_bytes"] / (1024 * 1024) if stats["size_bytes"] else 0
            index_size_mb = (
                stats["total_index_size_bytes"] / (1024 * 1024)
                if stats["total_index_size_bytes"]
                else 0
            )
            print(
                f"   🗃️  {collection}: {stats['document_count']:,} docs, "
                f"{size_mb:.2f}MB data, {index_size_mb:.2f}MB indexes"
            )

    # Check for deprecated collection
    messages_stats = await manager.show_collection_stats("messages")
    if "error" not in messages_stats and messages_stats["document_count"] == 0:
        print(
            f"\n⚠️  Deprecated 'messages' collection is empty and can be safely dropped"
        )
        print("   Run with --drop-deprecated to remove it")
    elif "error" not in messages_stats:
        print(
            f"\n⚠️  Deprecated 'messages' collection has {messages_stats['document_count']} documents"
        )
        print("   Manual migration required before cleanup")


if __name__ == "__main__":
    asyncio.run(main())

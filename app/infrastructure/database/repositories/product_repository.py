"""Product repository for database operations."""

from typing import List

from app.core.logging import get_logger
from app.domain.models.payment import (
    Product,
    ProductCategory,
    ProductCreate,
    ProductUpdate,
)
from app.infrastructure.database.repositories.base_repository import (
    BaseRepository,
    BaseRepositoryInterface,
)

logger = get_logger(__name__)


class ProductRepositoryInterface(
    BaseRepositoryInterface[Product, ProductCreate, ProductUpdate]
):
    """Product repository interface with domain-specific methods."""

    async def find_by_category(
        self, category: ProductCategory, limit: int = 50
    ) -> List[Product]:
        """Find products by category."""
        raise NotImplementedError

    async def find_active_products(self, limit: int = 50) -> List[Product]:
        """Find all active products."""
        raise NotImplementedError

    async def find_by_price_range(
        self, min_price: int, max_price: int, limit: int = 50
    ) -> List[Product]:
        """Find products by price range."""
        raise NotImplementedError

    async def search_products(self, search_term: str, limit: int = 20) -> List[Product]:
        """Search products by text."""
        raise NotImplementedError

    async def count_by_category(self, category: ProductCategory) -> int:
        """Count products by category."""
        raise NotImplementedError

    async def count_active_products(self) -> int:
        """Count active products."""
        raise NotImplementedError


class ProductRepository(
    BaseRepository[Product, ProductCreate, ProductUpdate], ProductRepositoryInterface
):
    """MongoDB product repository implementation."""

    def __init__(self):
        super().__init__("products", Product)

    async def find_by_category(
        self, category: ProductCategory, limit: int = 50
    ) -> List[Product]:
        """Find products by category."""
        try:
            cursor = (
                self.collection.find(
                    {"category": category, "is_active": True, "deleted_at": None}
                )
                .sort("created_at", -1)
                .limit(limit)
            )
            documents = await cursor.to_list(length=limit)

            products = []
            for doc in documents:
                converted_doc = self._convert_doc_ids_to_strings(doc)
                products.append(Product(**converted_doc))
            return products
        except Exception as e:
            logger.error(f"Failed to find products by category: {e}")
            return []

    async def find_active_products(self, limit: int = 50) -> List[Product]:
        """Find all active products."""
        try:
            cursor = (
                self.collection.find({"is_active": True, "deleted_at": None})
                .sort("created_at", -1)
                .limit(limit)
            )
            documents = await cursor.to_list(length=limit)

            products = []
            for doc in documents:
                converted_doc = self._convert_doc_ids_to_strings(doc)
                products.append(Product(**converted_doc))
            return products
        except Exception as e:
            logger.error(f"Failed to find active products: {e}")
            return []

    async def find_by_price_range(
        self, min_price: int, max_price: int, limit: int = 50
    ) -> List[Product]:
        """Find products by price range."""
        try:
            cursor = (
                self.collection.find(
                    {
                        "price": {"$gte": min_price, "$lte": max_price},
                        "is_active": True,
                        "deleted_at": None,
                    }
                )
                .sort("price", 1)
                .limit(limit)
            )

            documents = await cursor.to_list(length=limit)
            products = []
            for doc in documents:
                converted_doc = self._convert_doc_ids_to_strings(doc)
                products.append(Product(**converted_doc))
            return products
        except Exception as e:
            logger.error(f"Failed to find products by price range: {e}")
            return []

    async def search_products(self, search_term: str, limit: int = 20) -> List[Product]:
        """Search products by text."""
        try:
            cursor = (
                self.collection.find(
                    {
                        "$text": {"$search": search_term},
                        "is_active": True,
                        "deleted_at": None,
                    }
                )
                .sort("created_at", -1)
                .limit(limit)
            )

            documents = await cursor.to_list(length=limit)
            products = []
            for doc in documents:
                converted_doc = self._convert_doc_ids_to_strings(doc)
                products.append(Product(**converted_doc))
            return products
        except Exception as e:
            logger.error(f"Failed to search products: {e}")
            return []

    async def count_by_category(self, category: ProductCategory) -> int:
        """Count products by category."""
        try:
            count = await self.collection.count_documents(
                {"category": category, "is_active": True, "deleted_at": None}
            )
            return count
        except Exception as e:
            logger.error(f"Failed to count products by category: {e}")
            return 0

    async def count_active_products(self) -> int:
        """Count active products."""
        try:
            count = await self.collection.count_documents(
                {"is_active": True, "deleted_at": None}
            )
            return count
        except Exception as e:
            logger.error(f"Failed to count active products: {e}")
            return 0

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Product]:
        """Get all products with pagination (includes both active and inactive, excludes deleted)."""
        try:
            cursor = (
                self.collection.find({"deleted_at": None})
                .skip(skip)
                .limit(limit)
                .sort("created_at", -1)
            )

            products = []
            async for doc in cursor:
                converted_doc = self._convert_doc_ids_to_strings(doc)
                products.append(Product(**converted_doc))
            return products
        except Exception as e:
            logger.error(f"Failed to get all products: {e}")
            return []

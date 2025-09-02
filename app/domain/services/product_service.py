"""Product service for managing products and business logic."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from app.core.exceptions.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.utils.datetime_utils import ensure_datetime_or_now
from app.domain.models.payment import (
    Product,
    ProductCategory,
    ProductCreate,
    ProductUpdate,
)
from app.infrastructure.database.repositories.product_repository import (
    ProductRepository,
)

logger = get_logger(__name__)


class ProductService:
    """Service for handling product business logic."""

    def __init__(self, product_repository: Optional[ProductRepository] = None) -> None:
        """
        Initialize Product service with required dependencies.

        Args:
            product_repository: Repository for product operations
        """
        self.product_repository = product_repository or ProductRepository()

    async def create_product(self, request: ProductCreate) -> Product:
        """Create new product with business validation."""
        # Create product entity using ProductCreate data
        product_create = ProductCreate(
            title=request.title,
            description=request.description,
            price=request.price,
            currency=request.currency,
            credits=request.credits,
            category=request.category,
            photo_url=request.photo_url,
            feature_text=request.feature_text,
            show_feature=request.show_feature,
            stock_limit=request.stock_limit,
            meta=request.meta,
        )

        # Validate business rules (create temporary product for validation)
        temp_product = Product(**product_create.model_dump())
        self._validate_product_rules(temp_product)

        # Save product using repository (ObjectId will be generated automatically)
        product = await self.product_repository.create(product_create)

        logger.info(f"Product created with ID: {product.id}")
        return product

    async def get_product(self, product_id: str) -> Product:
        """Get product by ID."""
        product = await self.product_repository.get_by_id(product_id)
        if not product:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    async def get_products(self, limit: int = 50, offset: int = 0) -> List[Product]:
        """Get list of products with pagination."""
        # Note: offset parameter is available for future pagination implementation
        products = await self.product_repository.get_all(
            offset, limit
        )  # Use both parameters
        return products

    async def get_products_by_category(
        self, category: ProductCategory, limit: int = 50, active_only: bool = True
    ) -> List[Product]:
        """Get products by category."""
        if active_only:
            products = await self.product_repository.find_by_category(category, limit)
        else:
            # Get all products in category (including inactive)
            criteria = {"category": category, "deleted_at": None}
            products = await self.product_repository.find_by_criteria(
                criteria, limit=limit
            )
        return products

    async def get_active_products(
        self,
        category: Optional[ProductCategory] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Product]:
        """Get active products with optional category filtering."""
        if category:
            products = await self.product_repository.find_by_category(category, limit)
        else:
            products = await self.product_repository.find_active_products(limit)

        # Sort by creation time (using fallback for None values)
        return sorted(products, key=lambda p: ensure_datetime_or_now(p.created_at))

    async def update_product(self, product_id: str, updates: Dict[str, Any]) -> Product:
        """Update product with business validation."""
        product = await self.get_product(product_id)

        # Apply updates
        for field, value in updates.items():
            if hasattr(product, field):
                setattr(product, field, value)

        # Update timestamp
        product.updated_at = datetime.now(timezone.utc)

        # Validate updated product
        self._validate_product_rules(product)

        # Save changes
        await self.product_repository.update(product_id, ProductUpdate(**updates))

        return product

    async def update_product_structured(
        self, product_id: str, request: ProductUpdate
    ) -> Product:
        """Update product using structured request with business validation."""
        product = await self.get_product(product_id)

        # Convert request to dictionary, excluding None values
        updates = {
            k: v
            for k, v in request.model_dump(exclude_none=True).items()
            if v is not None
        }

        if not updates:
            raise ValidationError("No valid updates provided")

        # Apply updates
        for field, value in updates.items():
            if hasattr(product, field):
                setattr(product, field, value)

        # Update timestamp
        product.updated_at = datetime.now(timezone.utc)

        # Validate updated product
        self._validate_product_rules(product)

        # Save changes
        await self.product_repository.update(product_id, ProductUpdate(**updates))

        return product

    async def activate_product(self, product_id: str) -> Product:
        """Activate product (start sales)."""
        return await self.update_product(product_id, {"is_active": True})

    async def deactivate_product(self, product_id: str) -> Product:
        """Deactivate product (stop sales)."""
        return await self.update_product(product_id, {"is_active": False})

    async def set_featured_product(
        self, product_id: str, is_featured: bool = True
    ) -> Product:
        """Set product as featured."""
        return await self.update_product(product_id, {"is_featured": is_featured})

    async def update_stock(
        self, product_id: str, stock_limit: Optional[int]
    ) -> Product:
        """Update product stock limit."""
        if stock_limit is not None and stock_limit < 0:
            raise ValidationError("Stock limit cannot be negative")

        return await self.update_product(product_id, {"stock_limit": stock_limit})

    async def delete_product(self, product_id: str) -> bool:
        """Delete product (soft delete with deleted_at timestamp)."""
        try:
            # Use base repository's soft delete which sets deleted_at
            success = await self.product_repository.delete(product_id)
            return success
        except (NotFoundError, ValidationError):
            return False

    async def hard_delete_product(self, product_id: str) -> None:
        """Permanently delete product. Warning: This operation cannot be undone."""
        # Check if product exists
        await self.get_product(product_id)  # Will raise exception if not found

        # Execute hard delete
        success = await self.product_repository.delete(product_id)
        if not success:
            raise ValidationError(f"Failed to delete product {product_id}")

    async def get_products_by_price_range(
        self, min_price: int, max_price: int, limit: int = 50, active_only: bool = True
    ) -> List[Product]:
        """Get products within specified price range."""
        if active_only:
            return await self.product_repository.find_by_price_range(
                min_price, max_price, limit
            )
        else:
            # Get all products in price range (including inactive)
            criteria = {
                "price": {"$gte": min_price, "$lte": max_price},
                "deleted_at": None,
            }
            return await self.product_repository.find_by_criteria(criteria, limit=limit)

    async def get_credit_products(self, min_credits: int = 0) -> List[Product]:
        """Get products that reward credits."""
        criteria = {"is_active": True, "credits": {"$gt": min_credits}}

        return await self.product_repository.find_by_criteria(criteria)

    async def get_premium_products(self) -> List[Product]:
        """Get subscription products."""
        criteria = {"is_active": True, "category": ProductCategory.SUBSCRIPTION}

        return await self.product_repository.find_by_criteria(criteria)

    def _validate_product_rules(
        self, product: Union[Product, ProductCreate, ProductUpdate]
    ) -> None:
        """Validate product business rules."""
        # Price validation (only if price is set)
        if hasattr(product, "price") and product.price is not None:
            if product.price <= 0:
                raise ValidationError("Product price must be positive")

        # Credits validation (only if credits is set)
        if hasattr(product, "credits") and product.credits is not None:
            if product.credits < 0:
                raise ValidationError("Product credits cannot be negative")

        # Category-specific validation (only if both category and credits are set)
        if hasattr(product, "category") and product.category is not None:
            if product.category == ProductCategory.SUBSCRIPTION:
                credits = getattr(product, "credits", None)
                if credits is not None and credits == 0:
                    # Subscription products should specify duration in metadata
                    meta = getattr(product, "meta", None)
                    if not meta or "subscription_days" not in meta:
                        raise ValidationError(
                            "Subscription products must specify subscription_days in metadata"
                        )

            if product.category == ProductCategory.CREDITS:
                credits = getattr(product, "credits", None)
                if credits is not None and credits == 0:
                    raise ValidationError("Credit products must reward credits")

        # Stock validation (only if stock_limit is set)
        if hasattr(product, "stock_limit") and product.stock_limit is not None:
            if product.stock_limit < 0:
                raise ValidationError("Stock limit cannot be negative")

        # URL validation (only if photo_url is set)
        if hasattr(product, "photo_url") and product.photo_url:
            if not product.photo_url.startswith(("http://", "https://")):
                raise ValidationError("Photo URL must be a valid HTTP/HTTPS URL")

    def calculate_discount_price(
        self, product: Product, discount_percentage: float
    ) -> int:
        """Calculate discounted price."""
        if not (0 <= discount_percentage <= 100):
            raise ValidationError("Discount percentage must be between 0 and 100")

        discount_amount = int(product.price * (discount_percentage / 100))
        return max(1, product.price - discount_amount)  # Minimum price is 1

    def get_product_value_score(self, product: Product) -> float:
        """Calculate product value score (for recommendations). Credits to currency ratio."""
        if product.price == 0:
            return 0.0

        return product.credits / product.price

    async def get_product_statistics(self) -> Dict[str, Any]:
        """Get product statistics."""
        try:
            # Get all products
            all_products = await self.product_repository.get_all(limit=1000)
            active_products = await self.product_repository.find_active_products(1000)

            # Statistics by category
            category_counts = {}
            for product in all_products:
                category = product.category
                category_counts[category] = category_counts.get(category, 0) + 1

            # Price statistics
            if all_products:
                prices = [p.price for p in all_products]
                avg_price = sum(prices) / len(prices)
                min_price = min(prices)
                max_price = max(prices)
            else:
                avg_price = min_price = max_price = 0

            # Credits statistics
            if all_products:
                credits = [p.credits for p in all_products]
                avg_credits = sum(credits) / len(credits)
                total_credits = sum(credits)
            else:
                avg_credits = total_credits = 0

            return {
                "total_products": len(all_products),
                "active_products": len(active_products),
                "inactive_products": len(all_products) - len(active_products),
                "category_distribution": category_counts,
                "price_statistics": {
                    "average_price": round(avg_price, 2),
                    "min_price": min_price,
                    "max_price": max_price,
                    "currency": "XTR",
                },
                "credit_statistics": {
                    "average_credits": round(avg_credits, 2),
                    "total_credits": total_credits,
                },
            }
        except Exception as e:
            logger.error(f"Failed to get product statistics: {e}")
            raise

    async def update_product_sequences(
        self, sequence_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update product display sequences in batch."""
        updated_products = []
        updated_count = 0

        for item in sequence_data:
            product_id = item["product_id"]
            sequence = item["sequence"]

            try:
                # Validate product exists
                product = await self.get_product(product_id)

                # Update sequence
                await self.update_product(product_id, {"sequence": sequence})

                updated_products.append(
                    {
                        "product_id": product_id,
                        "sequence": sequence,
                        "title": product.title,
                    }
                )
                updated_count += 1

                logger.debug(f"Updated sequence for product {product_id} to {sequence}")

            except NotFoundError:
                logger.warning(f"Product {product_id} not found during sequence update")
                continue
            except Exception as e:
                logger.error(f"Failed to update sequence for product {product_id}: {e}")
                continue

        if updated_count == 0:
            raise ValidationError(
                "No products were updated. Check that product IDs are valid."
            )

        logger.info(f"Successfully updated sequences for {updated_count} products")

        return {"updated_count": updated_count, "updated_products": updated_products}

    async def get_products_sorted_by_sequence(
        self, limit: int = 50, offset: int = 0, active_only: bool = True
    ) -> List[Product]:
        """Get products sorted by sequence field (ascending)."""
        try:
            if active_only:
                # Get active products sorted by sequence
                criteria = {"is_active": True, "deleted_at": None}
                products = await self.product_repository.find_by_criteria(
                    criteria,
                    limit=limit,
                    skip=offset,
                    sort_field="sequence",
                    sort_direction=1,  # Ascending order
                )
            else:
                # Get all products sorted by sequence
                criteria = {"deleted_at": None}
                products = await self.product_repository.find_by_criteria(
                    criteria,
                    limit=limit,
                    skip=offset,
                    sort_field="sequence",
                    sort_direction=1,  # Ascending order
                )

            logger.debug(f"Retrieved {len(products)} products sorted by sequence")
            return products

        except Exception as e:
            logger.error(f"Failed to get products sorted by sequence: {e}")
            raise

    async def get_products_by_category_sorted(
        self, category: ProductCategory, limit: int = 50, active_only: bool = True
    ) -> List[Product]:
        """Get products by category sorted by sequence field (ascending)."""
        try:
            if active_only:
                criteria = {"category": category, "is_active": True, "deleted_at": None}
            else:
                criteria = {"category": category, "deleted_at": None}

            products = await self.product_repository.find_by_criteria(
                criteria,
                limit=limit,
                sort_field="sequence",
                sort_direction=1,  # Ascending order
            )

            logger.debug(
                f"Retrieved {len(products)} products in category {category} sorted by sequence"
            )
            return products

        except Exception as e:
            logger.error(f"Failed to get products by category sorted by sequence: {e}")
            raise

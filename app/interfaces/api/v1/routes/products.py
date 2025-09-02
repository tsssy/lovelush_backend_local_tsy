"""
Product management API endpoints for e-commerce operations.
Provides endpoints for creating, retrieving, updating, and managing e-commerce products
with support for categories, pricing, and activation status.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import ValidationError as PydanticValidationError

from app.core.dependencies import get_product_service
from app.core.exceptions.exceptions import (
    BaseCustomException,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.responses import ResponseHelper
from app.domain.models.payment import (
    ProductCategory,
    ProductCreate,
    ProductSortRequest,
    ProductUpdate,
)
from app.domain.services.product_service import ProductService
from app.infrastructure.security.dependencies import (
    get_current_admin_agent_only,
    get_current_user_or_active_agent,
)

router = APIRouter(prefix="/products", tags=["Products"])
logger = get_logger(__name__)


@router.post("/", response_model=dict, summary="Create new product")
async def create_product(
    request: ProductCreate,
    product_service: ProductService = Depends(get_product_service),
    current_agent: dict = Depends(get_current_admin_agent_only),
) -> Dict[str, Any]:
    """
    Create a new product.

    Creates a new e-commerce product with the provided information including
    title, description, price, credits, and category with proper validation.
    Only accessible by admin agents.

    Args:
        request: Product creation request with required fields
        product_service: Injected product service instance
        current_agent: Currently authenticated admin agent

    Returns:
        ResponseHelper.created with product data and success message

    Raises:
        HTTPException(400): Invalid input data or validation errors
        HTTPException(401): Agent not authenticated
        HTTPException(403): Agent does not have admin access or user attempted access
        HTTPException(409): Product with similar details already exists
        HTTPException(500): Internal server error during creation
    """
    try:
        product = await product_service.create_product(request)

        product_data = {
            "product_id": product.id,
            "title": product.title,
            "price": product.price,
            "credits": product.credits,
            "category": product.category,
            "is_active": product.is_active,
        }

        logger.info(
            "Product created successfully",
            extra={
                "product_id": product.id,
                "title": product.title,
                "created_by": current_agent["agent_id"],
            },
        )
        return ResponseHelper.created(
            data=product_data,
            msg="Product created successfully",
        )

    except PydanticValidationError as e:
        logger.warning("Product creation validation error", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except ValidationError as e:
        logger.warning(
            "Product creation business validation error", extra={"error": str(e)}
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BaseCustomException as e:
        logger.warning("Product creation business error", extra={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error creating product: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{product_id}", response_model=dict, summary="Get product by ID")
async def get_product(
    product_id: str = Path(..., min_length=24, max_length=24, description="Product ID"),
    product_service: ProductService = Depends(get_product_service),
    current_auth: dict = Depends(get_current_user_or_active_agent),
) -> Dict[str, Any]:
    """
    Get product details by ID.

    Retrieves detailed information about a specific product including
    all attributes, pricing, and availability status. Users can only see
    active products, while agents can see all products.

    Args:
        product_id: MongoDB ObjectId string of the product
        product_service: Injected product service instance
        current_auth: Currently authenticated user or agent

    Returns:
        ResponseHelper.success with product data

    Raises:
        HTTPException(400): Invalid product ID format
        HTTPException(401): User/Agent not authenticated
        HTTPException(404): Product not found or not available
        HTTPException(500): Internal server error during retrieval
    """
    try:
        product = await product_service.get_product(product_id)
        if not product:
            logger.warning(
                "Product not found",
                extra={
                    "product_id": product_id,
                    "auth_type": current_auth["type"],
                    "auth_id": current_auth.get("user_id")
                    or current_auth.get("agent_id"),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        # Users can only see active products, agents can see all
        if current_auth["type"] == "user" and not product.is_active:
            logger.warning(
                "Inactive product requested by user",
                extra={"product_id": product_id, "user_id": current_auth["user_id"]},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not available"
            )

        auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
        logger.debug(
            "Product retrieved",
            extra={
                "product_id": product_id,
                "auth_type": current_auth["type"],
                "auth_id": auth_id,
            },
        )
        return ResponseHelper.success(
            data=product, msg="Product retrieved successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
        logger.warning(
            "Invalid product ID format",
            extra={
                "product_id": product_id,
                "auth_type": current_auth["type"],
                "auth_id": auth_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID format"
        )
    except BaseCustomException as e:
        auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
        logger.warning(
            "Product retrieval business error",
            extra={
                "product_id": product_id,
                "auth_type": current_auth["type"],
                "auth_id": auth_id,
                "error": str(e),
            },
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving product: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/{product_id}", response_model=dict, summary="Update product")
async def update_product(
    request: ProductUpdate,
    product_id: str = Path(..., min_length=24, max_length=24, description="Product ID"),
    product_service: ProductService = Depends(get_product_service),
    current_agent: dict = Depends(get_current_admin_agent_only),
) -> Dict[str, Any]:
    """
    Update product information.

    Updates existing product information with the provided fields.
    Only non-null fields in the request will be updated.
    Only accessible by admin agents.

    Args:
        product_id: MongoDB ObjectId string of the product
        request: Product update request with optional fields
        product_service: Injected product service instance
        current_agent: Currently authenticated admin agent

    Returns:
        ResponseHelper.success with update confirmation

    Raises:
        HTTPException(400): Invalid input data, product ID, or no update data
        HTTPException(401): Agent not authenticated
        HTTPException(403): Agent does not have admin access or user attempted access
        HTTPException(404): Product not found
        HTTPException(500): Internal server error during update
    """
    try:
        # Build update data, excluding None values
        updates = {k: v for k, v in request.model_dump().items() if v is not None}

        if not updates:
            logger.warning(
                "No update data provided for product", extra={"product_id": product_id}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update data provided",
            )

        success = await product_service.update_product(product_id, updates)
        if not success:
            logger.warning(
                "Product not found or update failed", extra={"product_id": product_id}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found or update failed",
            )

        update_data = {"product_id": product_id, "updated_fields": list(updates.keys())}
        logger.info(
            "Product updated successfully",
            extra={"product_id": product_id, "updated_fields": list(updates.keys())},
        )

        return ResponseHelper.updated(
            data=update_data,
            msg="Product updated successfully",
        )

    except HTTPException:
        raise
    except ValidationError as e:
        logger.warning(
            "Product update validation error",
            extra={"product_id": product_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except BaseCustomException as e:
        logger.warning(
            "Product update business error",
            extra={"product_id": product_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error updating product: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{product_id}", response_model=dict, summary="Delete product")
async def delete_product(
    product_id: str = Path(..., min_length=24, max_length=24, description="Product ID"),
    product_service: ProductService = Depends(get_product_service),
    current_agent: dict = Depends(get_current_admin_agent_only),
) -> Dict[str, Any]:
    """
    Delete a product.

    Soft deletes the specified product, marking it as inactive while
    preserving the data for potential recovery.
    Only accessible by admin agents.

    Args:
        product_id: MongoDB ObjectId string of the product
        product_service: Injected product service instance
        current_agent: Currently authenticated admin agent

    Returns:
        ResponseHelper.deleted with deletion confirmation

    Raises:
        HTTPException(400): Invalid product ID format
        HTTPException(401): Agent not authenticated
        HTTPException(403): Agent does not have admin access or user attempted access
        HTTPException(404): Product not found or deletion failed
        HTTPException(500): Internal server error during deletion
    """
    try:
        success = await product_service.delete_product(product_id)
        if not success:
            logger.warning(
                "Product not found or deletion failed", extra={"product_id": product_id}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found or deletion failed",
            )

        logger.info("Product deleted successfully", extra={"product_id": product_id})
        return ResponseHelper.deleted(msg=f"Product {product_id} deleted successfully")

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid product ID format",
            extra={"product_id": product_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID format"
        )
    except BaseCustomException as e:
        logger.warning(
            "Product deletion business error",
            extra={"product_id": product_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error deleting product: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/", response_model=dict, summary="Get paginated products list")
async def get_products(
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of records to return"
    ),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    product_service: ProductService = Depends(get_product_service),
    current_auth: dict = Depends(get_current_user_or_active_agent),
) -> Dict[str, Any]:
    """
    Get paginated list of products.

    Retrieves a paginated list of products. Users see only active products,
    while agents can see all products.

    Args:
        limit: Maximum number of records to return (1-100)
        offset: Number of records to skip for pagination
        product_service: Injected product service instance
        current_auth: Currently authenticated user or agent

    Returns:
        ResponseHelper.success with paginated product data

    Raises:
        HTTPException(400): Invalid pagination parameters
        HTTPException(401): User/Agent not authenticated
        HTTPException(500): Internal server error during retrieval
    """
    try:
        # Users get only active products, agents get all products
        # Default to sorted by sequence to provide consistent ordering
        if current_auth["type"] == "user":
            products = await product_service.get_products_sorted_by_sequence(
                limit=limit, offset=offset, active_only=True
            )
        else:
            products = await product_service.get_products_sorted_by_sequence(
                limit=limit, offset=offset, active_only=False
            )

        products_data = {
            "products": [p for p in products],
            "count": len(products),
            "limit": limit,
            "offset": offset,
        }

        auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
        logger.debug(
            "Products list retrieved",
            extra={
                "count": len(products),
                "limit": limit,
                "offset": offset,
                "auth_type": current_auth["type"],
                "auth_id": auth_id,
            },
        )
        return ResponseHelper.success(
            data=products_data,
            msg="Product list retrieved successfully",
        )

    except ValueError as e:
        auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
        logger.warning(
            "Invalid pagination parameters",
            extra={
                "limit": limit,
                "offset": offset,
                "auth_type": current_auth["type"],
                "auth_id": auth_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pagination parameters: {str(e)}",
        )
    except BaseCustomException as e:
        logger.warning(
            "Products list retrieval business error", extra={"error": str(e)}
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving products list: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/category/{category}", response_model=dict, summary="Get products by category"
)
async def get_products_by_category(
    category: ProductCategory,
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of records to return"
    ),
    product_service: ProductService = Depends(get_product_service),
    current_auth: dict = Depends(get_current_user_or_active_agent),
) -> Dict[str, Any]:
    """
    Get products by category.

    Retrieves products filtered by the specified category.
    Users see only active products, agents see all products.

    Args:
        category: Product category to filter by
        limit: Maximum number of records to return (1-100)
        product_service: Injected product service instance
        current_auth: Currently authenticated user or agent

    Returns:
        ResponseHelper.success with categorized product data

    Raises:
        HTTPException(400): Invalid category or limit parameters
        HTTPException(401): User/Agent not authenticated
        HTTPException(500): Internal server error during retrieval
    """
    try:
        # Users get only active products, agents get all products
        # Use sequence-sorted products by category for consistent ordering
        products = await product_service.get_products_by_category_sorted(
            category, limit, active_only=(current_auth["type"] == "user")
        )

        category_data = {
            "category": category,
            "products": [p for p in products],
            "count": len(products),
        }

        auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
        logger.debug(
            "Products by category retrieved",
            extra={
                "category": category,
                "count": len(products),
                "auth_type": current_auth["type"],
                "auth_id": auth_id,
            },
        )
        return ResponseHelper.success(
            data=category_data,
            msg=f"Products in {category} category retrieved successfully",
        )

    except ValueError as e:
        auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
        logger.warning(
            "Invalid category or limit",
            extra={
                "category": category,
                "limit": limit,
                "auth_type": current_auth["type"],
                "auth_id": auth_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameters: {str(e)}",
        )
    except BaseCustomException as e:
        logger.warning(
            "Category products retrieval business error",
            extra={"category": category, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving products by category: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/active/list", response_model=dict, summary="Get active products only")
async def get_active_products(
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of records to return"
    ),
    product_service: ProductService = Depends(get_product_service),
    current_agent: dict = Depends(get_current_user_or_active_agent),
) -> Dict[str, Any]:
    """
    Get list of active products only.

    Retrieves products that are currently active and available for purchase.
    Excludes deactivated or deleted products.

    Args:
        limit: Maximum number of records to return (1-100)
        product_service: Injected product service instance
        current_agent: Currently authenticated admin agent

    Returns:
        ResponseHelper.success with active product data

    Raises:
        HTTPException(400): Invalid limit parameter
        HTTPException(401): Agent not authenticated
        HTTPException(500): Internal server error during retrieval
    """
    try:
        # Get active products sorted by sequence for consistent ordering
        products = await product_service.get_products_sorted_by_sequence(
            limit=limit, offset=0, active_only=True
        )

        active_data = {
            "active_products": [p for p in products],
            "count": len(products),
        }

        logger.debug(
            "Active products retrieved", extra={"count": len(products), "limit": limit}
        )
        return ResponseHelper.success(
            data=active_data,
            msg="Active products retrieved successfully",
        )

    except ValueError as e:
        logger.warning(
            "Invalid limit parameter", extra={"limit": limit, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid limit parameter: {str(e)}",
        )
    except BaseCustomException as e:
        logger.warning(
            "Active products retrieval business error", extra={"error": str(e)}
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving active products: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/price/range", response_model=dict, summary="Get products by price range")
async def get_products_by_price_range(
    min_price: int = Query(
        ..., ge=0, description="Minimum price in smallest currency unit"
    ),
    max_price: int = Query(
        ..., ge=0, description="Maximum price in smallest currency unit"
    ),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of records to return"
    ),
    product_service: ProductService = Depends(get_product_service),
    current_auth: dict = Depends(get_current_user_or_active_agent),
) -> Dict[str, Any]:
    """
    Get products within a price range.

    Retrieves products filtered by the specified price range with proper validation
    to ensure minimum price doesn't exceed maximum price. Users see only active
    products, agents see all products.

    Args:
        min_price: Minimum price in smallest currency unit (e.g., cents)
        max_price: Maximum price in smallest currency unit (e.g., cents)
        limit: Maximum number of records to return (1-100)
        product_service: Injected product service instance
        current_auth: Currently authenticated user or agent

    Returns:
        ResponseHelper.success with price-filtered product data

    Raises:
        HTTPException(400): Invalid price range or limit parameters
        HTTPException(401): User/Agent not authenticated
        HTTPException(500): Internal server error during retrieval
    """
    try:
        if min_price > max_price:
            auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
            logger.warning(
                "Invalid price range",
                extra={
                    "min_price": min_price,
                    "max_price": max_price,
                    "auth_type": current_auth["type"],
                    "auth_id": auth_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Minimum price cannot be greater than maximum price",
            )

        # Users get only active products, agents get all products
        active_only = current_auth["type"] == "user"
        products = await product_service.get_products_by_price_range(
            min_price, max_price, limit, active_only=active_only
        )

        auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
        logger.info(
            "Products retrieved by price range",
            extra={
                "min_price": min_price,
                "max_price": max_price,
                "product_count": len(products),
                "auth_type": current_auth["type"],
                "auth_id": auth_id,
            },
        )

        return ResponseHelper.success(
            data={
                "price_range": {"min": min_price, "max": max_price},
                "products": [p for p in products],
                "count": len(products),
            },
            msg="Products in price range retrieved successfully",
        )

    except HTTPException:
        raise
    except ValueError as e:
        auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
        logger.warning(
            "Invalid price range parameters",
            extra={
                "min_price": min_price,
                "max_price": max_price,
                "limit": limit,
                "auth_type": current_auth["type"],
                "auth_id": auth_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameters: {str(e)}",
        )
    except BaseCustomException as e:
        logger.warning(
            "Price range products retrieval business error", extra={"error": str(e)}
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(
            "Unexpected error retrieving products by price range: %s", str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/{product_id}/activate", response_model=dict, summary="Activate product")
async def activate_product(
    product_id: str = Path(..., min_length=24, max_length=24, description="Product ID"),
    product_service: ProductService = Depends(get_product_service),
    current_agent: dict = Depends(get_current_admin_agent_only),
) -> Dict[str, Any]:
    """
    Activate a product.

    Changes the product status to active, making it available for purchase.
    Typically used for administrative product management.

    Args:
        product_id: MongoDB ObjectId of the product to activate
        product_service: Injected product service instance
        current_agent: Currently authenticated admin agent

    Returns:
        ResponseHelper.success with activation confirmation

    Raises:
        HTTPException(400): Invalid product ID format
        HTTPException(401): Agent not authenticated
        HTTPException(403): Agent does not have admin access
        HTTPException(404): Product not found or activation failed
        HTTPException(500): Internal server error during activation
    """
    try:
        success = await product_service.update_product(product_id, {"is_active": True})
        if not success:
            logger.warning(
                "Product not found or activation failed",
                extra={"product_id": product_id, "agent_id": current_agent["agent_id"]},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found or activation failed",
            )

        logger.info(
            "Product activated successfully",
            extra={"product_id": product_id, "agent_id": current_agent["agent_id"]},
        )

        return ResponseHelper.success(
            data={"product_id": product_id, "status": "active"},
            msg="Product activated successfully",
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid product ID format for activation",
            extra={"product_id": product_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID format"
        )
    except BaseCustomException as e:
        logger.warning(
            "Product activation business error",
            extra={"product_id": product_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error activating product: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/{product_id}/deactivate", response_model=dict, summary="Deactivate product"
)
async def deactivate_product(
    product_id: str = Path(..., min_length=24, max_length=24, description="Product ID"),
    product_service: ProductService = Depends(get_product_service),
    current_agent: dict = Depends(get_current_admin_agent_only),
) -> Dict[str, Any]:
    """
    Deactivate a product.

    Changes the product status to inactive, removing it from active listings
    but preserving the product data for potential reactivation.

    Args:
        product_id: MongoDB ObjectId of the product to deactivate
        product_service: Injected product service instance
        current_agent: Currently authenticated admin agent

    Returns:
        ResponseHelper.success with deactivation confirmation

    Raises:
        HTTPException(400): Invalid product ID format
        HTTPException(401): Agent not authenticated
        HTTPException(403): Agent does not have admin access
        HTTPException(404): Product not found or deactivation failed
        HTTPException(500): Internal server error during deactivation
    """
    try:
        success = await product_service.update_product(product_id, {"is_active": False})
        if not success:
            logger.warning(
                "Product not found or deactivation failed",
                extra={"product_id": product_id, "agent_id": current_agent["agent_id"]},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found or deactivation failed",
            )

        logger.info(
            "Product deactivated successfully",
            extra={"product_id": product_id, "agent_id": current_agent["agent_id"]},
        )

        return ResponseHelper.success(
            data={"product_id": product_id, "status": "inactive"},
            msg="Product deactivated successfully",
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            "Invalid product ID format for deactivation",
            extra={"product_id": product_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID format"
        )
    except BaseCustomException as e:
        logger.warning(
            "Product deactivation business error",
            extra={"product_id": product_id, "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error deactivating product: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/stats/overview", response_model=dict, summary="Get product statistics")
async def get_product_statistics(
    product_service: ProductService = Depends(get_product_service),
    current_agent: dict = Depends(get_current_admin_agent_only),
) -> Dict[str, Any]:
    """
    Get product statistics overview.

    Retrieves comprehensive statistics about products including counts by status,
    category distribution, pricing information, and other metrics.

    Args:
        product_service: Injected product service instance
        current_agent: Currently authenticated admin agent

    Returns:
        ResponseHelper.success with product statistics data

    Raises:
        HTTPException(401): Agent not authenticated
        HTTPException(403): Agent does not have admin access
        HTTPException(500): Internal server error during statistics calculation
    """
    try:
        stats = await product_service.get_product_statistics()

        logger.info(
            "Product statistics retrieved",
            extra={"agent_id": current_agent["agent_id"]},
        )
        return ResponseHelper.success(
            data=stats, msg="Product statistics retrieved successfully"
        )

    except BaseCustomException as e:
        logger.warning(
            "Product statistics retrieval business error", extra={"error": str(e)}
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving product statistics: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/sort", response_model=dict, summary="Update product display order")
async def update_product_sort_order(
    request: ProductSortRequest,
    product_service: ProductService = Depends(get_product_service),
    current_agent: dict = Depends(get_current_admin_agent_only),
) -> Dict[str, Any]:
    """
    Update the display order sequence for multiple products.

    Allows frontend to store the sort order by updating the sequence field
    for multiple products in a single request. Lower sequence numbers
    appear first in sorted lists.

    Args:
        request: Product sort request with product IDs and their new sequences
        product_service: Injected product service instance
        current_agent: Currently authenticated admin agent

    Returns:
        ResponseHelper.success with update confirmation and affected products

    Raises:
        HTTPException(400): Invalid request data or validation errors
        HTTPException(401): Agent not authenticated
        HTTPException(403): Agent does not have admin access
        HTTPException(404): One or more products not found
        HTTPException(500): Internal server error during update
    """
    try:
        # Validate the request data
        if not request.validate_sequences():
            logger.warning(
                "Invalid product sequence data",
                extra={
                    "agent_id": current_agent["agent_id"],
                    "data": request.product_sequences,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid product sequence data. Each entry must have product_id and sequence (non-negative integer)",
            )

        # Update the sequences
        result = await product_service.update_product_sequences(
            request.product_sequences
        )

        logger.info(
            "Product sequences updated successfully",
            extra={
                "agent_id": current_agent["agent_id"],
                "updated_count": result["updated_count"],
                "product_ids": [
                    item["product_id"] for item in request.product_sequences
                ],
            },
        )

        return ResponseHelper.success(
            data=result,
            msg=f"Successfully updated sequence for {result['updated_count']} products",
        )

    except HTTPException:
        raise
    except ValidationError as e:
        logger.warning(
            "Product sequence update validation error",
            extra={"agent_id": current_agent["agent_id"], "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except BaseCustomException as e:
        logger.warning(
            "Product sequence update business error",
            extra={"agent_id": current_agent["agent_id"], "error": str(e)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error updating product sequences: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/list/sorted", response_model=dict, summary="Get products sorted by sequence"
)
async def get_products_sorted(
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of records to return"
    ),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    product_service: ProductService = Depends(get_product_service),
    current_auth: dict = Depends(get_current_user_or_active_agent),
) -> Dict[str, Any]:
    """
    Get products sorted by their sequence field.

    Retrieves products ordered by their sequence value (ascending).
    Products with lower sequence numbers appear first.
    Users see only active products, agents see all products.

    Args:
        limit: Maximum number of records to return (1-100)
        offset: Number of records to skip for pagination
        product_service: Injected product service instance
        current_auth: Currently authenticated user or agent

    Returns:
        ResponseHelper.success with sorted product data

    Raises:
        HTTPException(400): Invalid pagination parameters
        HTTPException(401): User/Agent not authenticated
        HTTPException(500): Internal server error during retrieval
    """
    try:
        # Users get only active products, agents get all products
        active_only = current_auth["type"] == "user"
        products = await product_service.get_products_sorted_by_sequence(
            limit=limit, offset=offset, active_only=active_only
        )

        products_data = {
            "products": [p for p in products],
            "count": len(products),
            "limit": limit,
            "offset": offset,
            "sorted_by": "sequence",
        }

        auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
        logger.debug(
            "Sorted products list retrieved",
            extra={
                "count": len(products),
                "limit": limit,
                "offset": offset,
                "auth_type": current_auth["type"],
                "auth_id": auth_id,
            },
        )

        return ResponseHelper.success(
            data=products_data, msg="Sorted product list retrieved successfully"
        )

    except ValueError as e:
        auth_id = current_auth.get("user_id") or current_auth.get("agent_id")
        logger.warning(
            "Invalid pagination parameters for sorted products",
            extra={
                "limit": limit,
                "offset": offset,
                "auth_type": current_auth["type"],
                "auth_id": auth_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pagination parameters: {str(e)}",
        )
    except BaseCustomException as e:
        logger.warning(
            "Sorted products list retrieval business error", extra={"error": str(e)}
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving sorted products list: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

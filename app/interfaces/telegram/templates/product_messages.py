"""Product message templates for Telegram bot."""

from dataclasses import dataclass
from typing import Optional

from app.domain.models.payment import Product


@dataclass
class ProductListTemplate:
    """Template for product list messages."""

    header: str = "🛒 <b>Available Products{page_info}</b>\n"
    product_item: str = "{number}. <b>{title}</b> - {price} {currency}"
    credits_suffix: str = " (+{credits} credits)"
    description: str = "   <i>{description}</i>"
    footer: str = "👆 Tap any product to view details and purchase!"
    no_products: str = (
        "🛒 No products available at the moment. Please check back later!"
    )

    def format_header(self, page: int = 0, has_pagination: bool = False) -> str:
        """Format the header with optional page info."""
        page_info = f" (Page {page + 1})" if page > 0 or has_pagination else ""
        return self.header.format(page_info=page_info)

    def format_product_item(self, number: int, product: Product) -> str:
        """Format a single product item."""
        # Clean title for HTML display
        clean_title = (
            self._clean_html(product.title) if product.title else f"Product {number}"
        )
        currency_display = (
            product.currency.value
            if hasattr(product.currency, "value")
            else str(product.currency)
        )

        item_text = self.product_item.format(
            number=number,
            title=clean_title,
            price=product.price,
            currency=currency_display,
        )

        # Add credits if available
        if product.credits > 0:
            item_text += self.credits_suffix.format(credits=product.credits)

        return item_text

    def format_description(
        self, product: Product, max_length: int = 100
    ) -> Optional[str]:
        """Format product description with truncation."""
        if not product.description:
            return None

        clean_desc = self._clean_html(product.description)
        if len(clean_desc) > max_length:
            clean_desc = clean_desc[:max_length] + "..."

        return self.description.format(description=clean_desc)

    @staticmethod
    def _clean_html(text: str) -> str:
        """Clean text for HTML display."""
        return text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")


@dataclass
class ProductDetailTemplate:
    """Template for product detail messages."""

    template: str = """🛍️ <b>{title}</b>

📝 <b>Description</b>: {description}

💰 <b>Price</b>: {price} {currency}
🪙 <b>Credits</b>: {credits_text}
📂 <b>Category</b>: {category}{stock_info}

💡 Tap "Buy Now" to purchase this product!"""

    no_credits: str = "No credits"
    credits_format: str = "+{credits} credits"
    stock_info: str = "\n📦 <b>Stock</b>: {stock} remaining"

    # Error messages
    not_found: str = "❌ Product not found. Please select a product from the list."
    not_available: str = (
        "❌ This product is no longer available. Please select another product."
    )

    def format_product_detail(self, product: Product) -> str:
        """Format complete product detail message."""
        # Clean content for HTML
        clean_title = self._clean_html(product.title) if product.title else "Product"
        clean_description = (
            self._clean_html(product.description) if product.description else ""
        )
        currency_display = (
            product.currency.value
            if hasattr(product.currency, "value")
            else str(product.currency)
        )

        # Format credits
        credits_text = (
            self.credits_format.format(credits=product.credits)
            if product.credits > 0
            else self.no_credits
        )

        # Format stock info
        stock_info = ""
        if product.stock_limit is not None:
            stock_info = self.stock_info.format(stock=product.stock_limit)

        return self.template.format(
            title=clean_title,
            description=clean_description,
            price=product.price,
            currency=currency_display,
            credits_text=credits_text,
            category=product.category.value.title(),
            stock_info=stock_info,
        )

    @staticmethod
    def _clean_html(text: str) -> str:
        """Clean text for HTML display."""
        return text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")


@dataclass
class PaymentTemplate:
    """Template for payment confirmation messages."""

    template: str = """🛒 <b>Payment Confirmation</b>

📦 <b>Product</b>: {title}
💰 <b>Price</b>: {price} {currency}
🪙 <b>Credits you'll receive</b>: +{credits}

💳 <b>Your Current Credits</b>: {current_balance}
🎉 <b>Credits after purchase</b>: {new_balance}

💡 Complete your payment using the button below:"""

    # Error messages
    payment_error: str = "❌ Payment error. Please try again."
    user_not_found: str = "❌ User not found. Please start over with /start."
    product_unavailable: str = (
        "❌ Product is no longer available. Please select another product."
    )
    processing_error: str = "❌ Error processing payment. Please try again later."

    def format_payment_confirmation(
        self, product: Product, current_balance: int, new_balance: int
    ) -> str:
        """Format payment confirmation message."""
        clean_title = self._clean_html(product.title) if product.title else "Product"
        currency_display = (
            product.currency.value
            if hasattr(product.currency, "value")
            else str(product.currency)
        )

        return self.template.format(
            title=clean_title,
            price=product.price,
            currency=currency_display,
            credits=product.credits,
            current_balance=current_balance,
            new_balance=new_balance,
        )

    @staticmethod
    def _clean_html(text: str) -> str:
        """Clean text for HTML display."""
        return text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")


@dataclass
class ButtonTemplate:
    """Templates for button texts."""

    # Product list buttons
    product_button: str = "{number}. {title} - {price} {currency}"

    # Pagination buttons
    previous_button: str = "⬅️ Previous"
    next_button: str = "Next ➡️"

    # Product detail buttons
    buy_button: str = "💳 Buy Now - {price} {currency}"
    back_to_list: str = "⬅️ Back to Products"

    # Payment buttons
    pay_button: str = "💳 Pay {price} {currency}"
    back_to_product: str = "⬅️ Back to Product"
    cancel_button: str = "❌ Cancel"

    def format_product_button(self, number: int, product: Product) -> str:
        """Format product selection button."""
        clean_title = (
            self._clean_html(product.title) if product.title else f"Product {number}"
        )
        currency_display = (
            product.currency.value
            if hasattr(product.currency, "value")
            else str(product.currency)
        )

        return self.product_button.format(
            number=number,
            title=clean_title,
            price=product.price,
            currency=currency_display,
        )

    def format_buy_button(self, product: Product) -> str:
        """Format buy now button."""
        currency_display = (
            product.currency.value
            if hasattr(product.currency, "value")
            else str(product.currency)
        )
        return self.buy_button.format(price=product.price, currency=currency_display)

    def format_pay_button(self, product: Product) -> str:
        """Format payment button."""
        currency_display = (
            product.currency.value
            if hasattr(product.currency, "value")
            else str(product.currency)
        )
        return self.pay_button.format(price=product.price, currency=currency_display)

    @staticmethod
    def _clean_html(text: str) -> str:
        """Clean text for HTML display."""
        return text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")


# Global template instances
product_list_template = ProductListTemplate()
product_detail_template = ProductDetailTemplate()
payment_template = PaymentTemplate()
button_template = ButtonTemplate()

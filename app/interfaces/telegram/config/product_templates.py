"""Configuration for product message templates."""

from app.interfaces.telegram.templates.product_messages import (
    ButtonTemplate,
    PaymentTemplate,
    ProductDetailTemplate,
    ProductListTemplate,
)


class ProductTemplateConfig:
    """Configuration class for easy template customization."""

    @staticmethod
    def get_product_list_template() -> ProductListTemplate:
        """Get customized product list template."""
        return ProductListTemplate(
            header="🛒 <b>Available Products{page_info}</b>\n",
            product_item="{number}. <b>{title}</b> - {price} {currency}",
            credits_suffix=" (+{credits} credits)",
            description="   <i>{description}</i>",
            footer="👆 Tap any product to view details and purchase!",
            no_products="🛒 No products available at the moment. Please check back later!",
        )

    @staticmethod
    def get_product_detail_template() -> ProductDetailTemplate:
        """Get customized product detail template."""
        return ProductDetailTemplate(
            template="""🛍️ <b>{title}</b>

📝 <b>Description</b>: {description}

💰 <b>Price</b>: {price} {currency}
🪙 <b>Credits</b>: {credits_text}
📂 <b>Category</b>: {category}{stock_info}

💡 Tap "Buy Now" to purchase this product!""",
            no_credits="No credits",
            credits_format="+{credits} credits",
            stock_info="\n📦 <b>Stock</b>: {stock} remaining",
            not_found="❌ Product not found. Please select a product from the list.",
            not_available="❌ This product is no longer available. Please select another product.",
        )

    @staticmethod
    def get_payment_template() -> PaymentTemplate:
        """Get customized payment template."""
        return PaymentTemplate(
            template="""🛒 <b>Payment Confirmation</b>

📦 <b>Product</b>: {title}
💰 <b>Price</b>: {price} {currency}
🪙 <b>Credits you'll receive</b>: +{credits}

💳 <b>Your Current Credits</b>: {current_balance}
🎉 <b>Credits after purchase</b>: {new_balance}

💡 Complete your payment using the button below:""",
            payment_error="❌ Payment error. Please try again.",
            user_not_found="❌ User not found. Please start over with /start.",
            product_unavailable="❌ Product is no longer available. Please select another product.",
            processing_error="❌ Error processing payment. Please try again later.",
        )

    @staticmethod
    def get_button_template() -> ButtonTemplate:
        """Get customized button template."""
        return ButtonTemplate(
            product_button="{number}. {title} - {price} {currency}",
            previous_button="⬅️ Previous",
            next_button="Next ➡️",
            buy_button="💳 Buy Now - {price} {currency}",
            back_to_list="⬅️ Back to Products",
            pay_button="💳 Pay {price} {currency}",
            back_to_product="⬅️ Back to Product",
            cancel_button="❌ Cancel",
        )


# Easy customization examples:


# For seasonal themes:
def get_christmas_template() -> ProductListTemplate:
    """Example: Christmas themed template."""
    return ProductListTemplate(
        header="🎄 <b>Christmas Special Products{page_info}</b> 🎅\n",
        product_item="🎁 {number}. <b>{title}</b> - {price} {currency}",
        credits_suffix=" (🪙 +{credits} holiday credits)",
        footer="🎄 Tap any product for Christmas deals! 🎁",
    )


# For different languages:
def get_chinese_template() -> ProductListTemplate:
    """Example: Chinese language template."""
    return ProductListTemplate(
        header="🛒 <b>可用产品{page_info}</b>\n",
        product_item="{number}. <b>{title}</b> - {price} {currency}",
        credits_suffix=" (+{credits} 积分)",
        footer="👆 点击任意产品查看详情并购买！",
        no_products="🛒 暂无产品，请稍后再查看！",
    )


# For different business models:
def get_subscription_template() -> ProductListTemplate:
    """Example: Subscription focused template."""
    return ProductListTemplate(
        header="💎 <b>Premium Subscriptions{page_info}</b>\n",
        product_item="⭐ {number}. <b>{title}</b> - {price} {currency}/month",
        credits_suffix=" (includes {credits} monthly credits)",
        footer="🚀 Choose your subscription plan!",
    )

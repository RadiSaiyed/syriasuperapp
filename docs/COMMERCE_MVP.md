Commerce — MVP Scope

Goals
- Simple marketplace with shops, products, carts, and orders.
- Optional payment request handoff to Payments API (internal dev endpoint).

Endpoints (Commerce API)
- POST `/auth/request_otp`, `/auth/verify_otp` — dev login
- GET `/shops` — list shops (seeded in dev)
- GET `/shops/{id}/products` — list products for a shop
- GET `/cart` — view cart
- POST `/cart/items` — add item (product_id, qty)
- PUT `/cart/items/{item_id}?qty=…` — change qty or remove when qty<=0
- POST `/cart/clear` — clear cart
- POST `/orders/checkout` — create order from cart
- GET `/orders` — list my orders

Data Model (simplified)
- User(id, phone, name)
- Shop(id, name, description)
- Product(id, shop_id, name, description, price_cents, stock_qty, active)
- Cart(id, user_id, updated_at), CartItem(id, cart_id, product_id, qty)
- Order(id, user_id, shop_id, status, total_cents, payment_request_id?), OrderItem(order_id, product_id, name_snapshot, price_cents_snapshot, qty, subtotal_cents)

Dev Notes
- Seed shops/products on first call in dev.
- Payments handoff is best-effort; failures are ignored for dev.


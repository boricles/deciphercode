# DecipherCode Analysis Report

**Target:** `/home/user/projects/ecommerce-api`
**Files:** 142
**Lines of code:** 18,340

## Languages

| Language | Files |
|---|---|
| Python | 98 |
| HTML | 18 |
| JavaScript | 12 |
| YAML | 8 |
| SQL | 4 |
| Shell | 2 |

## Frameworks

- Django
- Django REST Framework
- Celery
- Docker

## Architecture

Monolithic MVC (Django). The project follows Django's standard app-based architecture with a central `settings.py`, URL routing in `urls.py`, and business logic split across 6 Django apps. Background task processing is handled by Celery with Redis as the broker.

## Components

- `accounts/` - User authentication, registration, and profile management
- `products/` - Product catalog with categories, search, and image handling
- `orders/` - Order processing, cart management, and checkout flow
- `payments/` - Stripe integration for payment processing
- `shipping/` - Shipping rate calculation and tracking
- `notifications/` - Email and SMS notifications via Celery tasks

## API Routes

- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - JWT token authentication
- `GET /api/v1/products/` - List products with filtering and pagination
- `GET /api/v1/products/{id}/` - Product detail
- `POST /api/v1/cart/` - Add item to cart
- `POST /api/v1/orders/` - Create order from cart
- `POST /api/v1/payments/webhook` - Stripe webhook handler
- `GET /api/v1/orders/{id}/tracking` - Order tracking info

## Database Models

- `User` (accounts) - Extended Django user with profile fields
- `Product` (products) - name, description, price, category, images
- `Category` (products) - Hierarchical product categories
- `Order` (orders) - user, status, total, shipping_address
- `OrderItem` (orders) - order, product, quantity, price
- `Payment` (payments) - order, stripe_id, status, amount
- `ShipmentTracking` (shipping) - order, carrier, tracking_number

## Environment Variables

- `SECRET_KEY` - Django secret key
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection for Celery
- `STRIPE_SECRET_KEY` - Stripe API key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook verification
- `AWS_S3_BUCKET` - S3 bucket for product images
- `SENDGRID_API_KEY` - Email service API key

## Dead Code Candidates

- `products/views_old.py` - Appears to be a backup of the original views, not imported anywhere
- `shipping/fedex.py` - FedEx integration module, no references found in codebase
- `accounts/management/commands/seed_users.py` - Dev seed script, unused in production

## Key Observations

- The project has good separation of concerns across Django apps
- No test files found; test coverage appears to be zero
- `payments/views.py` handles Stripe webhooks without signature verification in some code paths
- Database queries in `products/views.py` could benefit from `select_related` to avoid N+1 queries
- Settings file contains hardcoded values that should be environment variables
- No API versioning strategy beyond the `/api/v1/` prefix

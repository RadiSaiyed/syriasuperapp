Car Market Service

FastAPI service for a car marketplace: listings with images and status, favorites, offers with payment handoff, chat and seller reviews.

Run locally
1) Copy `.env.example` to `.env` and adjust.
2) Start Postgres and Redis: `docker compose up -d db redis`
3) Run API: `docker compose up --build api`
4) Swagger: http://localhost:8086/docs

Auth (DEV)
- OTP is stubbed as 123456
- Use phone `+963xxxxxxxxx`

Features
- Listings: create, browse/search with filters (make/model/year/city/price), my listings, detail view
- Listing images: add image URLs to listings
- Listing status: mark sold/hide/activate
- Favorites: add/remove, list
- Offers: create, view my offers, view offers per listing (seller), accept/reject/cancel
- Payments (DEV): on accept, create internal payment request buyer→seller
- Chat: buyer↔seller per listing (buyers with an offer or the seller)
- Seller reviews: buyers rate seller after accepted offer

API (selection)
- Listings: `POST /listings`, `GET /listings`, `GET /listings/mine`, `GET /listings/{id}`
- Images: `POST /listings/{id}/images`
- Listing status: `POST /listings/{id}/mark_sold|hide|activate`
- Favorites: `POST /favorites/{listing_id}`, `DELETE /favorites/{listing_id}`, `GET /favorites`
- Offers: `POST /offers/listing/{listing_id}`, `GET /offers`, `GET /offers/listing/{listing_id}`, `POST /offers/{offer_id}/accept|reject|cancel`, `POST /offers/{offer_id}/rate`
- Chat: `GET/POST /chats/listing/{listing_id}`

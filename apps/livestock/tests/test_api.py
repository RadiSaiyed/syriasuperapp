import os
from fastapi.testclient import TestClient

os.environ.setdefault("DB_URL", os.getenv("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"))

from app.main import app  # noqa: E402


client = TestClient(app)


def _auth(phone: str):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": "Buyer"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _auth_role(phone: str, role: str):
    r = client.post("/auth/request_otp", json={"phone": phone})
    assert r.status_code == 200
    r = client.post("/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": role.capitalize(), "role": role})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_and_seed_and_basic_flows():
    assert client.get("/health").status_code == 200

    # seed
    r = client.post("/admin/seed")
    assert r.status_code == 200

    # buyer login
    h = _auth("+963901000002")

    # browse products
    r = client.get("/market/products")
    assert r.status_code == 200
    prods = r.json()["products"]
    assert len(prods) >= 1
    pid = prods[0]["id"]
    # order
    r = client.post(f"/market/products/{pid}/order", headers=h, json={"qty": 1})
    assert r.status_code == 200

    # browse animals
    r = client.get("/market/animals")
    assert r.status_code == 200
    animals = r.json()["animals"]
    assert len(animals) >= 1
    aid = animals[0]["id"]
    r = client.post(f"/market/animals/{aid}/order", headers=h)
    assert r.status_code == 200


def test_favorites_and_auctions_flow():
    # seed exists
    client.post("/admin/seed")
    # buyer
    hb = _auth("+963901000003")
    # list animals and favorite first
    r = client.get("/market/animals")
    assert r.status_code == 200
    animals = r.json()["animals"]
    assert animals, r.text
    aid = animals[0]["id"]
    assert client.post(f"/market/animals/{aid}/favorite", headers=hb).status_code == 200
    r = client.get("/market/animals/favorites", headers=hb)
    assert r.status_code == 200 and len(r.json()["animals"]) >= 1

    # seller login from seed
    hs = _auth("+963900000310")
    # create auction for the animal if still available; otherwise pick another
    # attempt auction creation (may fail if already sold)
    import datetime as dt
    ends = (dt.datetime.utcnow() + dt.timedelta(minutes=5)).isoformat() + "Z"
    ra = client.post(
        "/seller/auctions",
        headers=hs,
        json={"animal_id": aid, "starting_price_cents": 1000, "ends_at_iso": ends},
    )
    if ra.status_code == 200:
        auc = ra.json()
        # place bid as buyer
        rb = client.post(f"/market/auctions/{auc['id']}/bid", headers=hb, json={"amount_cents": 1500})
        assert rb.status_code == 200, rb.text
        # close as seller
        rc = client.post(f"/seller/auctions/{auc['id']}/close", headers=hs)
        assert rc.status_code == 200
    else:
        # if auction couldn't be created (e.g., sold), just assert listing endpoints still work
        assert client.get("/market/auctions").status_code == 200


def test_seller_delete_endpoints():
    client.post("/admin/seed")
    hs = _auth_role("+963901000099", "seller")
    # create ranch
    r = client.post("/seller/ranch", headers=hs, json={"name": "R1", "location": "Test"})
    if r.status_code not in (200, 400):
        assert False, r.text
    # create animal and delete
    r = client.post("/seller/animals", headers=hs, json={"species": "cow", "price_cents": 1000})
    assert r.status_code == 200
    aid = r.json()["id"]
    assert client.delete(f"/seller/animals/{aid}", headers=hs).status_code == 200
    # create product and delete
    r = client.post("/seller/products", headers=hs, json={"product_type": "milk", "unit": "liter", "quantity": 10, "price_per_unit_cents": 500})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert client.delete(f"/seller/products/{pid}", headers=hs).status_code == 200

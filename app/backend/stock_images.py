"""Bundled stock images served from /static/img/stock/."""

STOCK_DIR = "img/stock"

STOCK_HERO = f"{STOCK_DIR}/hero.jpg"
STOCK_ABOUT = f"{STOCK_DIR}/about.jpg"

STOCK_GALLERY = [
    (f"{STOCK_DIR}/gallery-01.jpg", "A soft private treatment space with calming light"),
    (f"{STOCK_DIR}/gallery-02.jpg", "A serene feminine wellness atmosphere"),
    (f"{STOCK_DIR}/gallery-03.jpg", "Premium oils and soothing wellness details"),
    (f"{STOCK_DIR}/gallery-04.jpg", "A calming massage moment in progress"),
    (f"{STOCK_DIR}/gallery-05.jpg", "Soft textures curated for comfort"),
    (f"{STOCK_DIR}/gallery-06.jpg", "A warm restorative setup prepared with care"),
    (f"{STOCK_DIR}/gallery-07.jpg", "A quiet corner designed for rest and renewal"),
    (f"{STOCK_DIR}/gallery-08.jpg", "A signature treatment scene with premium linens"),
    (f"{STOCK_DIR}/gallery-09.jpg", "Soft lighting in a calm private setting"),
    (f"{STOCK_DIR}/gallery-10.jpg", "A feminine wellness space with a luxury feel"),
    (f"{STOCK_DIR}/gallery-11.jpg", "Wellness details styled with softness"),
    (f"{STOCK_DIR}/gallery-12.jpg", "A tranquil moment captured in a private session"),
]

STOCK_MASSEUSES = [
    {
        "name": "Sophia Lane",
        "bio": "Specializing in Swedish and restorative bodywork with a calm, intuitive touch.",
        "specialties": ["Swedish", "Relaxation", "Stress relief"],
        "image": f"{STOCK_DIR}/team-01.jpg",
    },
    {
        "name": "Mia Chen",
        "bio": "Deep tissue specialist focused on mobility, recovery, and personalized care.",
        "specialties": ["Deep tissue", "Sports recovery", "Mobility"],
        "image": f"{STOCK_DIR}/team-02.jpg",
    },
    {
        "name": "Elena Rose",
        "bio": "Luxury wellness rituals crafted for comfort, privacy, and full-body renewal.",
        "specialties": ["Full body", "Aromatherapy", "Premium care"],
        "image": f"{STOCK_DIR}/team-03.jpg",
    },
]

"""BE-15: нагрузочный тест поиска GET /found-items.

Токен каждый виртуальный пользователь получает у dev-SSO (POST /dev-sso/token).
"""

import random
from datetime import date, timedelta

from locust import HttpUser, between, task

CATEGORIES = ["electronics", "documents", "keys", "wallet", "bag", "clothing"]
LOCATIONS = ["library", "main_building", "dormitory", "cafeteria", "sports_hall", "parking"]
COLORS = ["black", "white", "blue", "red", "gray", "green"]
QUERIES = ["iPhone", "keys", "Backpack", "Wallet", "card", "charger"]


class StudentUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        response = self.client.post("/dev-sso/token", params={"role": "student"}, name="dev-sso token")
        self.client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})

    @task(3)
    def by_category(self):
        self.client.get(
            "/found-items",
            params={"category": random.choice(CATEGORIES), "limit": 20},
            name="/found-items?category",
        )

    @task(3)
    def by_text(self):
        self.client.get(
            "/found-items",
            params={"q": random.choice(QUERIES), "limit": 20},
            name="/found-items?q",
        )

    @task(2)
    def combined(self):
        today = date.today()
        self.client.get(
            "/found-items",
            params={
                "category": random.choice(CATEGORIES),
                "location": random.choice(LOCATIONS),
                "color": random.choice(COLORS),
                "date_from": (today - timedelta(days=60)).isoformat(),
                "date_to": today.isoformat(),
                "limit": 20,
            },
            name="/found-items?combined",
        )

    @task(1)
    def deep_page(self):
        self.client.get(
            "/found-items",
            params={"limit": 20, "offset": random.randint(0, 19_000)},
            name="/found-items?deep_offset",
        )

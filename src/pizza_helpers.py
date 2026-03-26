from __future__ import annotations

import logging
from typing import Any

from opentelemetry import trace

logger = logging.getLogger("pizza_demo")


def normalize_order(payload: Any, tracer: trace.Tracer) -> dict[str, Any]:
    with tracer.start_as_current_span("normalize_order") as span:
        normalized = {
            "size": payload.size.strip().lower(),
            "crust": payload.crust.strip().lower(),
            "toppings": [t.strip().lower() for t in payload.toppings],
            "quantity": payload.quantity,
        }

        span.set_attribute("pizza.size", normalized["size"])
        span.set_attribute("pizza.crust", normalized["crust"])
        span.set_attribute("pizza.quantity", normalized["quantity"])
        span.set_attribute("pizza.topping_count", len(normalized["toppings"]))

        return normalized


def validate_order(order: dict[str, Any], menu: dict[str, Any], tracer: trace.Tracer) -> None:
    with tracer.start_as_current_span("validate_order") as span:
        size = order["size"]
        crust = order["crust"]
        toppings = order["toppings"]

        if size not in menu["sizes"]:
            span.set_attribute("pizza.valid", False)
            logger.warning("invalid pizza size", extra={"size": size})
            raise ValueError(f"Invalid size: {size}")

        if crust not in menu["crusts"]:
            span.set_attribute("pizza.valid", False)
            logger.warning("invalid pizza crust", extra={"crust": crust})
            raise ValueError(f"Invalid crust: {crust}")

        invalid_toppings = [t for t in toppings if t not in menu["toppings"]]
        if invalid_toppings:
            span.set_attribute("pizza.valid", False)
            logger.warning(
                "invalid pizza toppings",
                extra={"invalid_toppings": ",".join(invalid_toppings)},
            )
            raise ValueError(f"Invalid toppings: {', '.join(invalid_toppings)}")

        span.set_attribute("pizza.valid", True)
        logger.info(
            "order validated",
            extra={
                "size": size,
                "crust": crust,
                "topping_count": len(toppings),
                "quantity": order["quantity"],
            },
        )


def calculate_price(
    order: dict[str, Any], menu: dict[str, Any], tracer: trace.Tracer
) -> tuple[float, float]:
    with tracer.start_as_current_span("calculate_price") as span:
        size_price = menu["sizes"][order["size"]]
        crust_price = menu["crusts"][order["crust"]]
        toppings_price = sum(menu["toppings"][t] for t in order["toppings"])

        price_per_pizza = round(size_price + crust_price + toppings_price, 2)
        subtotal = round(price_per_pizza * order["quantity"], 2)

        span.set_attribute("pizza.price_per_pizza", price_per_pizza)
        span.set_attribute("pizza.subtotal", subtotal)

        logger.info(
            "price calculated",
            extra={
                "price_per_pizza": price_per_pizza,
                "subtotal": subtotal,
            },
        )

        return price_per_pizza, subtotal


def estimate_timing(order: dict[str, Any], tracer: trace.Tracer) -> tuple[float, float, float]:
    with tracer.start_as_current_span("estimate_timing") as span:
        topping_count = len(order["toppings"])
        quantity = order["quantity"]

        prep_time = 8.0 + topping_count * 1.5 + (quantity - 1) * 2.0
        if order["crust"] == "deep-dish":
            bake_time = 18.0
        elif order["crust"] == "hand-tossed":
            bake_time = 14.0
        else:
            bake_time = 12.0

        total_time = round(prep_time + bake_time, 2)
        prep_time = round(prep_time, 2)
        bake_time = round(bake_time, 2)

        span.set_attribute("pizza.prep_time_seconds", prep_time)
        span.set_attribute("pizza.bake_time_seconds", bake_time)
        span.set_attribute("pizza.total_estimated_time_seconds", total_time)

        logger.info(
            "timing estimated",
            extra={
                "prep_time_seconds": prep_time,
                "bake_time_seconds": bake_time,
                "total_estimated_time_seconds": total_time,
            },
        )

        return prep_time, bake_time, total_time


def prepare_pizza(order: dict[str, Any], prep_time: float, tracer: trace.Tracer) -> None:
    with tracer.start_as_current_span("prepare_pizza") as span:
        span.set_attribute("pizza.prep_time_seconds", prep_time)
        span.set_attribute("pizza.quantity", order["quantity"])
        logger.info(
            "pizza prepared",
            extra={
                "size": order["size"],
                "crust": order["crust"],
                "prep_time_seconds": prep_time,
            },
        )


def bake_pizza(order: dict[str, Any], bake_time: float, tracer: trace.Tracer) -> None:
    with tracer.start_as_current_span("bake_pizza") as span:
        span.set_attribute("pizza.bake_time_seconds", bake_time)
        span.set_attribute("pizza.crust", order["crust"])
        logger.info(
            "pizza baked",
            extra={
                "crust": order["crust"],
                "bake_time_seconds": bake_time,
            },
        )


def persist_order(
    order_summary: dict[str, Any], orders: list[dict[str, Any]], tracer: trace.Tracer
) -> None:
    with tracer.start_as_current_span("persist_order") as span:
        orders.append(order_summary)
        span.set_attribute("pizza.order_id", order_summary["order_id"])
        span.set_attribute("pizza.total_orders", len(orders))
        logger.info(
            "order persisted",
            extra={
                "order_id": order_summary["order_id"],
                "total_orders": len(orders),
            },
        )

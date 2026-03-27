from __future__ import annotations
import logging
from typing import Any
from opentelemetry import trace

# Instantiating the logger
logger = logging.getLogger('pizza_api')

def normalize_order(payload: Any, tracer: trace.Tracer) -> dict[str, Any]:
    '''
    Normalizes the pizza order details
    
    Inputs:
        - payload (Any): The original payload from the API
        - tracer (trace.Tracer): The OpenTelemetry tracer for logging spans

    Returns:
        - normalized (dict): The normalized pizza order details
    '''
    
    # Starting the "noramlize order" span
    with tracer.start_as_current_span('normalize_order') as span:

        # Normalizing the order details
        normalized = {
            'size': payload.size.strip().lower(),
            'crust': payload.crust.strip().lower(),
            'toppings': [t.strip().lower() for t in payload.toppings],
            'quantity': payload.quantity,
        }

        # Setting all the relevant span attributes
        span.set_attribute('pizza.size', normalized['size'])
        span.set_attribute('pizza.crust', normalized['crust'])
        span.set_attribute('pizza.quantity', normalized['quantity'])
        span.set_attribute('pizza.topping_count', len(normalized['toppings']))

        return normalized
    

def calculate_price(order: dict[str, Any], menu: dict[str, Any], tracer: trace.Tracer) -> tuple[float, float]:
    '''
    Calculates the price per pizza and overall subtotal

    Inputs:
        - order (dict): The pizza order details
        - menu (dict): The pizza menu along with its prices
        - tracer (trace.Tracer): The OpenTelemetry tracer for logging spans

    Returns:
        - price_per_pizza (float): The price per pizza
        - subtotal (float): The subtotal of all the pizzas
    '''

    # Starting the "calculate price" span
    with tracer.start_as_current_span('calculate_price') as span:

        # Getting the size, crust, and toppings prices
        size_price = menu['sizes'][order['size']]
        crust_price = menu['crusts'][order['crust']]
        toppings_price = sum(menu['toppings'][t] for t in order['toppings'])

        # Calculating the price per pizza and subtotal
        price_per_pizza = round(size_price + crust_price + toppings_price, 2)
        subtotal = round(price_per_pizza * order['quantity'], 2)

        # Setting all the relevant span attributes
        span.set_attribute('pizza.price_per_pizza', price_per_pizza)
        span.set_attribute('pizza.subtotal', subtotal)

        # Logging the price calculation information
        logger.info(
            msg = 'price calculated',
            extra = {
                'price_per_pizza': price_per_pizza,
                'subtotal': subtotal,
            },
        )

        return price_per_pizza, subtotal
    


def estimate_timing(order: dict[str, Any], tracer: trace.Tracer) -> tuple[float, float, float]:
    '''
    Estimates the timing to make a pizza from start to finish based on order details

    Inputs:
        - order (dict): The pizza order details
        - tracer (trace.Tracer): The OpenTelemetry tracer for logging spans

    Returns:
        - prep_time (float): The prep time in seconds
        - bake_time (float): The bake time in seconds
        - total_time (float): The total time to make the pizza
    '''

    # Starting the "estimate timing" span
    with tracer.start_as_current_span('estimate_timing') as span:

        # Getting the topping count and quantity count
        topping_count = len(order['toppings'])
        quantity = order['quantity']

        # Calcuating the prep time of the pizza
        prep_time = 8.0 + topping_count * 1.5 + (quantity - 1) * 2.0

        # Calculating the bake time of the pizza
        if order['crust'] == 'deep-dish':
            bake_time = 18.0
        elif order['crust'] == 'hand-tossed':
            bake_time = 14.0
        else:
            bake_time = 12.0

        # Calculating the total time, rounded to 2 places
        total_time = round(prep_time + bake_time, 2)

        # Rounding the prep and bake time to 2 places
        prep_time = round(prep_time, 2)
        bake_time = round(bake_time, 2)

        # Setting all the relevant span attributes
        span.set_attribute('pizza.prep_time_seconds', prep_time)
        span.set_attribute('pizza.bake_time_seconds', bake_time)
        span.set_attribute('pizza.total_estimated_time_seconds', total_time)


        # Logging the estimated timing information
        logger.info(
            msg = 'estimated timing',
            extra = {
                'prep_time_seconds': prep_time,
                'bake_time_seconds': bake_time,
                'total_estimated_time_seconds': total_time,
            },
        )

        return prep_time, bake_time, total_time
    

def prepare_pizza(order: dict[str, Any], prep_time: float, tracer: trace.Tracer) -> None:
    '''
    Records pizza preparation details for observability

    Inputs:
        - order (dict): The pizza order details
        - prep_time (float): The prep time in seconds
        - tracer (trace.Tracer): The OpenTelemetry tracer for logging spans

    Returns:
        - (N/A)
    '''
    # Starting the "prepare pizza" span
    with tracer.start_as_current_span('prepare_pizza') as span:

        # Setting all the relevant span attributes
        span.set_attribute('pizza.prep_time_seconds', prep_time)
        span.set_attribute('pizza.quantity', order['quantity'])
        
        # Logging the "prepared pizza" info
        logger.info(
            msg = 'pizza prepared',
            extra = {
                'size': order['size'],
                'crust': order['crust'],
                'prep_time_seconds': prep_time,
            },
        )


def bake_pizza(order: dict[str, Any], bake_time: float, tracer: trace.Tracer) -> None:
    '''
    Records pizza baking details for observability

    Inputs:
        - order (dict): The pizza order details
        - bake_time (float): The bake time in seconds
        - tracer (trace.Tracer): The OpenTelemetry tracer for logging spans

    Returns:
        - (N/A)
    '''

    # Starting the "bake pizza" span
    with tracer.start_as_current_span('bake_pizza') as span:

        # Setting all the relevant span attributes
        span.set_attribute('pizza.bake_time_seconds', bake_time)
        span.set_attribute('pizza.crust', order['crust'])

        # Logging the "bake pizza" info
        logger.info(
            msg = 'pizza baked',
            extra = {
                'crust': order['crust'],
                'bake_time_seconds': bake_time,
            },
        )



def persist_order(order_summary: dict[str, Any], orders: list[dict[str, Any]], tracer: trace.Tracer) -> None:
    '''
    Persists the completed order summary

    Inputs:
        - order_summary (dict): The finalized summary of the pizza order
        - orders (list[dict]): The in-memory collection of all orders
        - tracer (trace.Tracer): The OpenTelemetry tracer for logging spans

    Returns:
        - (N/A)
    '''

    # Starting the "persist order" span
    with tracer.start_as_current_span('persist_order') as span:

        # Appending the current order to all orders
        orders.append(order_summary)

        # Setting all the relevant span attributes
        span.set_attribute('pizza.order_id', order_summary['order_id'])
        span.set_attribute('pizza.total_orders', len(orders))

        # Logging the "order persisted" info
        logger.info(
            msg = 'order persisted',
            extra = {
                'order_id': order_summary['order_id'],
                'total_orders': len(orders),
            },
        )
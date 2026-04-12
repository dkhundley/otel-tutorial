# Importing base Python libraries
from __future__ import annotations
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# Importing third party Python libraries
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from opentelemetry import metrics, trace

# Importing our own custom code
from otel_config import configure_otel
from pizza_helpers import *



## DATA LOAD / DATA MODEL INSTANTIATION
## -------------------------------------------------------------------------------------------------
# Loading the pizza menu
with open('pizza_menu.json', 'r', encoding='utf-8') as menu_file:
    PIZZA_MENU = json.load(menu_file)

# Instantiating a list to hold the pizza orders
pizza_orders = []

# Instantiating a data model for pizza order requests
class PizzaOrderRequest(BaseModel):
    size: str = Field(..., description = 'small, medium, or large')
    crust: str = Field(..., description = 'thin, hand-tossed, or deep-dish')
    toppings: list[str] = Field(default_factory = list)
    quantity: int = Field(default = 1, ge = 1, le = 10)

# Instantiating a data model for pizza order responses
class PizzaOrderResponse(BaseModel):
    order_id: int
    size: str
    crust: str
    toppings: list[str]
    quantity: int
    price_per_pizza: float
    subtotal: float
    prep_time_seconds: float
    bake_time_seconds: float
    total_estimated_time_seconds: float
    status: str



## OPENTELEMETRY SETUP
## -------------------------------------------------------------------------------------------------
# Initializing the OTEL configuration
configure_otel()

# Instantiating the OTEL tracer, meter, and logger
tracer = trace.get_tracer('pizza_api.tracer')
meter = metrics.get_meter('pizza_api.meter')
logger = logging.getLogger('pizza_api')



## OPENTELEMETRY METER SETUP
## -------------------------------------------------------------------------------------------------
# Instantiating an OpenTelemetry counter to track the number of HTTP requests
http_request_counter = meter.create_counter(
    name = 'http.server.requests',
    description = 'Number of HTTP requests'
)

# Instantiating an OpenTelemetry histogram to track the duration of HTTP requests
http_request_duration = meter.create_histogram(
    name = 'http.server.duration',
    description = 'Duration of HTTP requests (in ms)',
    unit = 'ms'
)

# Instantiating an OpenTelemetry counter to track the number of pizza orders placed
pizza_orders_counter = meter.create_counter(
    name = 'pizza.orders',
    description = 'Number of pizza orders placed'
)

# Instantiating an OpenTelemetry counter to keep track of the total revenue across all the pizza orders placed
pizza_revenue_counter = meter.create_counter(
    name = 'pizza.revenue',
    description = 'Total pizza revenue (in usd)',
    unit = 'usd'
)

# Instantiating an OpenTelemetry histogram to track the distribution of pizza order subtotals
pizza_order_value_histogram = meter.create_histogram(
    name = 'pizza.order_value',
    description = 'Distribution of pizza order subtotals (in usd)',
    unit = 'usd'
)

# Instantiating an OpenTelemetry hisogram to track the estimated prep time
pizza_prep_time_histogram = meter.create_histogram(
    name = 'pizza.prep_time',
    description = 'Estimated pizza prep time (in seconds)',
    unit = 's'
)

# Instantiating an OpenTelemetry hisogram to track the estimated bake time
pizza_bake_time_histogram = meter.create_histogram(
    name = 'pizza.bake_time',
    description = 'Estimated pizza bake time (in seconds)',
    unit = 's'
)



## FASTAPI SETUP
## -------------------------------------------------------------------------------------------------
# Setting the async context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('Starting the API...')
    yield
    logger.info('Shutting down the API...')

# Instanitiating the FastAPI API object
pizza_api = FastAPI(title = 'Pizza API', lifespan = lifespan)

# Defining the middleware configuration
@pizza_api.middleware('http')
async def telemetry_middleware(request: Request, call_next):

    start = time.perf_counter()
    route = request.url.path
    method = request.method
    status_code = 500

    # Incrementing the HTTP request counter
    http_request_counter.add(
        amount = 1,
        attributes = {
            'http.method': method,
            'http.route': route
        }
    )

    logger.info(
        msg = 'Request started',
        extra = {
            'http.method': method,
            'http.route': route
        }
    )

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    
    except Exception:
        logger.exception(
            msg = 'Unhandled exception during request',
            extra = {
                'http.method': method,
                'http.route': route
            }
        )

    finally:

        # Calculating the duration of the pizza order
        pizza_order_duration = round(number = (time.perf_counter() - start) * 1000.0, ndigits = 2)

        # Recording the duration of the pizza order
        http_request_duration.record(
            pizza_order_duration,
            {
                'http.method': method,
                'http:route': route,
                'http.status_code': status_code,
            }
        )

        # Logging that the request has finished
        logger.info(
            msg = 'Request finished',
            extra = {
                'http.method': method,
                'http.route': route,
                'http.status_code': status_code,
                'duration_ms': pizza_order_duration
            }
        )



## API ENDPOINTS
## -------------------------------------------------------------------------------------------------
# Defining a GET endpoint to share the menu with the customer
@pizza_api.get('/menu')
async def get_menu():

    # Starting an OTEL span for getting the menu
    with tracer.start_as_current_span('get_menu'):

        # Logging that the menu was requested
        logger.info('Menu requested')

        return PIZZA_MENU
    


# Defining a POST endpoint to create a new pizza order
@pizza_api.post('/order', response_model = PizzaOrderResponse)
async def create_pizza_order(payload: PizzaOrderRequest):

    # Starting an OTEL span for creating the pizza order
    with tracer.start_as_current_span('create_pizza_order') as span:

        # Logging that the order was received and order details
        logger.info(
            msg = 'Order received',
            extra = {
                'size': payload.size,
                'crust': payload.crust,
                'quantity': payload.quantity,
                'topping_count': len(payload.toppings)
            }
        )

        # Normalizing the pizza order
        pizza_order = normalize_order(payload = payload, tracer = tracer)

        # Associating specific attributes to our current span
        span.set_attribute(key = 'pizza.size', value = pizza_order['size'])
        span.set_attribute(key = 'pizza.crust', value = pizza_order['crust'])
        span.set_attribute(key = 'pizza.quantity', value = pizza_order['quantity'])
        span.set_attribute(key = 'pizza.topping_count', value = len(pizza_order['toppings']))
        
        # Calculating the price per pizza and subtotal
        price_per_pizza, subtotal = calculate_price(order = pizza_order, menu = PIZZA_MENU, tracer = tracer)

        # Calculating prep time, bake time, and total time
        prep_time, bake_time, total_time = estimate_timing(order = pizza_order, tracer = tracer)

        # Prepping the pizza
        prepare_pizza(order = pizza_order, prep_time = prep_time, tracer = tracer)

        # Baking the pizza
        bake_pizza(order = pizza_order, bake_time = bake_time, tracer = tracer)

        # Setting a simple order ID
        order_id = len(pizza_orders) + 1

        # Creating the order summary
        order_summary = {
            'order_id': order_id,
            'size': pizza_order['size'],
            'crust': pizza_order['crust'],
            'toppings': pizza_order['toppings'],
            'quantity': pizza_order['quantity'],
            'price_per_pizza': price_per_pizza,
            'subtotal': subtotal,
            'prep_time_seconds': prep_time,
            'bake_time_seconds': bake_time,
            'total_estimated_time_seconds': total_time,
            'status': 'Ready for pickup!'
        }

        # Persisting the order
        persist_order(order_summary = order_summary, orders = pizza_orders, tracer = tracer)

        # Incrementing the pizza order counter
        pizza_orders_counter.add(
            amount = pizza_order['quantity'],
            attributes = {
                'size': pizza_order['size'],
                'crust': pizza_order['crust']
            }
        )

        # Incrementing the revenue counter
        pizza_revenue_counter.add(
            amount = subtotal,
            attributes = {
                'size': pizza_order['size'],
                'crust': pizza_order['crust']
            }
        )

        # Updating the order histogram object
        pizza_order_value_histogram.record(
            amount = subtotal,
            attributes = {
                'size': pizza_order['size'],
                'crust': pizza_order['crust']
            }
        )

        # Updating the prep time histogram object
        pizza_prep_time_histogram.record(
            amount = prep_time,
            attributes = {
            'size': pizza_order['size'],
            'crust': pizza_order['crust']
            }
        )

        # Updating the bake time histogram object
        pizza_bake_time_histogram.record(
            amount = bake_time,
            attributes = {
            'size': pizza_order['size'],
            'crust': pizza_order['crust']
            }
        )

        # Logging that the order was completed
        logger.info(
            msg = 'Order completed',
            extra = {
            'order_id': order_id,
            'subtotal': subtotal,
            'total_estimated_time_seconds': total_time
            }
        )

        return PizzaOrderResponse(**order_summary)


@pizza_api.get('/stats')
async def get_stats():

    # Starting an OTEL span for getting stats
    with tracer.start_as_current_span('get_stats') as span:

        # Calculating stats from pizza orders
        total_orders = len(pizza_orders)
        total_revenue = round(sum(order['subtotal'] for order in pizza_orders), 2)
        total_pizzas = sum(order['quantity'] for order in pizza_orders)
        avg_order_value = round(total_revenue / total_orders, 2) if total_orders else 0.0

        # Associating specific attributes to our current span
        span.set_attribute(key = 'pizza.total_orders', value = total_orders)
        span.set_attribute(key = 'pizza.total_revenue', value = total_revenue)
        span.set_attribute(key = 'pizza.total_pizzas', value = total_pizzas)
        span.set_attribute(key = 'pizza.avg_order_value', value = avg_order_value)

        # Logging that stats were requested
        logger.info(
            msg = 'Stats requested',
            extra = {
                'total_orders': total_orders,
                'total_revenue': total_revenue,
                'total_pizzas': total_pizzas,
                'avg_order_value': avg_order_value
            }
        )

        return {
            'total_orders': total_orders,
            'total_pizzas': total_pizzas,
            'total_revenue': total_revenue,
            'average_order_value': avg_order_value
        }


@pizza_api.get('/health')
async def health():

    # Logging the health check
    logger.info('Health check')

    return {'status': 'ok'}
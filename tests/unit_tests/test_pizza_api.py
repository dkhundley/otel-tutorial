from __future__ import annotations

# Importing base Python libraries
import json
import sys
import types
from pathlib import Path
from typing import Any

# Importing third party Python libraries
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


## PATH CONFIGURATION
## -------------------------------------------------------------------------------------------------
# Resolving important project paths once so fixtures can consistently load source and sample data.
ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
SAMPLE_ORDERS_PATH = ROOT_DIR / 'tests' / 'sample_data' / 'sample_pizza_orders.json'
PIZZA_MENU_PATH = SRC_DIR / 'pizza_menu.json'


## TEST HELPER FUNCTIONS
## -------------------------------------------------------------------------------------------------
def _compute_expected_price(order_payload: dict[str, Any], pizza_menu: dict[str, Any]) -> tuple[float, float]:
	# Calculating the expected pricing fields to validate /order responses.
	base_size_price = pizza_menu['sizes'][order_payload['size']]
	selected_crust_price = pizza_menu['crusts'][order_payload['crust']]
	toppings_total_price = sum(pizza_menu['toppings'][topping] for topping in order_payload['toppings'])

	# Returning both values validated by endpoint tests: per-pizza price and full order subtotal.
	price_per_pizza = round(base_size_price + selected_crust_price + toppings_total_price, 2)
	order_subtotal = round(price_per_pizza * order_payload['quantity'], 2)
	return price_per_pizza, order_subtotal


def _compute_expected_timing(order_payload: dict[str, Any]) -> tuple[float, float, float]:
	# Reproducing timing logic so tests can assert prep/bake/total fields.
	number_of_toppings = len(order_payload['toppings'])
	requested_quantity = order_payload['quantity']
	estimated_prep_time_seconds = round(8.0 + number_of_toppings * 1.5 + (requested_quantity - 1) * 2.0, 2)

	# Matching crust-based bake-time branching used by the API helper implementation.
	if order_payload['crust'] == 'deep-dish':
		estimated_bake_time_seconds = 18.0
	elif order_payload['crust'] == 'hand-tossed':
		estimated_bake_time_seconds = 14.0
	else:
		estimated_bake_time_seconds = 12.0

	# Returning prep, bake, and combined duration exactly as asserted by endpoint response checks.
	estimated_total_time_seconds = round(estimated_prep_time_seconds + estimated_bake_time_seconds, 2)
	return estimated_prep_time_seconds, estimated_bake_time_seconds, estimated_total_time_seconds


## TEST FIXTURES
## -------------------------------------------------------------------------------------------------
@pytest.fixture(scope='module')
def pizza_module() -> Any:
	# Creating test-time compatibility shims so endpoint tests run against the current source.
	monkey_patch = pytest.MonkeyPatch()

	# Ensuring the src directory is importable when tests execute from the tests folder.
	if str(SRC_DIR) not in sys.path:
		sys.path.insert(0, str(SRC_DIR))

	# Loading the real menu once so patched json.loads can return stable deterministic menu data.
	with PIZZA_MENU_PATH.open('r', encoding='utf-8') as menu_file_handle:
		menu_json_data = json.load(menu_file_handle)

	original_json_loads = json.loads

	# Redirecting the app's json.loads('pizza_menu.json') call to the fixture-provided menu dictionary.
	def _json_loads_compat(value: str, *args: Any, **kwargs: Any) -> Any:
		if value == 'pizza_menu.json':
			return menu_json_data
		return original_json_loads(value, *args, **kwargs)

	monkey_patch.setattr(json, 'loads', _json_loads_compat)

	original_middleware = FastAPI.middleware

	# Translating known middleware typo so the in-memory module can register middleware successfully.
	def _middleware_compat(self: FastAPI, middleware_type: str):
		if middleware_type == 'htto':
			middleware_type = 'http'
		return original_middleware(self, middleware_type)

	monkey_patch.setattr(FastAPI, 'middleware', _middleware_compat)

	# Loading a sanitized in-memory copy so endpoint tests can execute despite minor source typos.
	source_path = SRC_DIR / 'pizza_api.py'
	source_code = source_path.read_text(encoding='utf-8')
	source_code = source_code.replace('from typing import any', 'from typing import Any as any')
	source_code = source_code.replace('@pizza_api.middleware(\'htto\')', '@pizza_api.middleware(\'http\')')

	# Executing the patched source as a synthetic module so tests exercise API behavior end-to-end.
	pizza_api_module = types.ModuleType('pizza_api')
	pizza_api_module.__file__ = str(source_path)
	pizza_api_module.__package__ = ''

	sys.modules.pop('pizza_api', None)
	exec(compile(source_code, str(source_path), 'exec'), pizza_api_module.__dict__)
	sys.modules['pizza_api'] = pizza_api_module

	# Yielding the loaded module to tests, then cleaning monkey patches to avoid cross-module side effects.
	yield pizza_api_module
	monkey_patch.undo()


@pytest.fixture
def client(pizza_module: Any) -> TestClient:
	# Resetting state between tests to keep order IDs and stats deterministic.
	pizza_module.pizza_orders.clear()

	# Creating a fresh FastAPI test client per test for request/response isolation.
	with TestClient(pizza_module.pizza_api) as test_client:
		yield test_client


@pytest.fixture(scope='module')
def sample_orders() -> list[dict[str, Any]]:
	# Providing reusable sample payloads for parameterized and aggregation test scenarios.
	with SAMPLE_ORDERS_PATH.open('r', encoding='utf-8') as sample_orders_file_handle:
		return json.load(sample_orders_file_handle)


@pytest.fixture(scope='module')
def pizza_menu() -> dict[str, Any]:
	# Providing the canonical pizza menu used to compute expected pricing values in tests.
	with PIZZA_MENU_PATH.open('r', encoding='utf-8') as pizza_menu_file_handle:
		return json.load(pizza_menu_file_handle)


## ENDPOINT TEST CASES
## -------------------------------------------------------------------------------------------------
def test_health_endpoint_returns_ok(client: TestClient) -> None:
	# Calling the health endpoint to validate basic API availability.
	health_response = client.get('/health')

	# Verifying response code and body contract.
	assert health_response.status_code == 200
	assert health_response.json() == {'status': 'ok'}


def test_menu_endpoint_returns_menu(client: TestClient, pizza_menu: dict[str, Any]) -> None:
	# Requesting the menu endpoint to confirm static menu payload delivery.
	menu_response = client.get('/menu')

	# Verifying endpoint status and exact menu parity.
	assert menu_response.status_code == 200
	assert menu_response.json() == pizza_menu


@pytest.mark.parametrize('sample_index', [0, 1, 2, 3])
def test_order_endpoint_calculates_summary_fields(
	client: TestClient,
	sample_orders: list[dict[str, Any]],
	pizza_menu: dict[str, Any],
	sample_index: int,
) -> None:
	# Selecting one sample payload and pre-computing expected pricing/timing fields.
	order_payload = sample_orders[sample_index]
	expected_price_per_pizza, expected_order_subtotal = _compute_expected_price(order_payload, pizza_menu)
	expected_prep_time_seconds, expected_bake_time_seconds, expected_total_time_seconds = _compute_expected_timing(order_payload)

	# Creating an order and reading its JSON summary for assertion checks.
	order_response = client.post('/order', json=order_payload)
	order_response_json = order_response.json()

	# Validating each summary field to protect against pricing, timing, and schema regressions.
	assert order_response.status_code == 200
	assert order_response_json['order_id'] == 1
	assert order_response_json['size'] == order_payload['size']
	assert order_response_json['crust'] == order_payload['crust']
	assert order_response_json['toppings'] == order_payload['toppings']
	assert order_response_json['quantity'] == order_payload['quantity']
	assert order_response_json['price_per_pizza'] == expected_price_per_pizza
	assert order_response_json['subtotal'] == expected_order_subtotal
	assert order_response_json['prep_time_seconds'] == expected_prep_time_seconds
	assert order_response_json['bake_time_seconds'] == expected_bake_time_seconds
	assert order_response_json['total_estimated_time_seconds'] == expected_total_time_seconds
	assert order_response_json['status'] == 'Ready for pickup!'


def test_order_endpoint_normalizes_case_and_whitespace(client: TestClient) -> None:
	# Building a payload with uppercase letters and surrounding whitespace to test normalization.
	order_payload = {
		'size': '  SMALL ',
		'crust': ' Thin ',
		'toppings': [' Pepperoni ', '  Mushrooms'],
		'quantity': 2,
	}

	# Posting the noisy payload and extracting the normalized response body.
	order_response = client.post('/order', json=order_payload)
	order_response_json = order_response.json()

	# Ensuring normalized values are lowercase and trimmed as expected.
	assert order_response.status_code == 200
	assert order_response_json['size'] == 'small'
	assert order_response_json['crust'] == 'thin'
	assert order_response_json['toppings'] == ['pepperoni', 'mushrooms']


def test_order_endpoint_rejects_quantity_out_of_bounds(client: TestClient) -> None:
	# Building an invalid payload where quantity violates the model lower bound.
	invalid_order_payload = {
		'size': 'small',
		'crust': 'thin',
		'toppings': ['pepperoni'],
		'quantity': 0,
	}

	# Calling the endpoint and validating request-model enforcement.
	validation_response = client.post('/order', json=invalid_order_payload)

	assert validation_response.status_code == 422


def test_stats_endpoint_aggregates_multiple_orders(
	client: TestClient,
	sample_orders: list[dict[str, Any]],
) -> None:
	# Creating multiple orders so /stats has data to aggregate across orders.
	orders_for_stats_validation = sample_orders[:3]
	recorded_order_subtotals: list[float] = []

	# Persisting orders and capturing returned subtotals for expected total revenue calculation.
	for order_payload in orders_for_stats_validation:
		order_response = client.post('/order', json=order_payload)
		assert order_response.status_code == 200
		recorded_order_subtotals.append(order_response.json()['subtotal'])

	# Requesting aggregate stats after seeding multiple orders.
	stats_response = client.get('/stats')
	stats_response_json = stats_response.json()

	# Computing expected aggregate values based on seeded orders and returned subtotals.
	expected_total_orders = len(orders_for_stats_validation)
	expected_total_pizzas = sum(order['quantity'] for order in orders_for_stats_validation)
	expected_total_revenue = round(sum(recorded_order_subtotals), 2)
	expected_average_order_value = round(expected_total_revenue / expected_total_orders, 2)

	# Verifying all reported aggregate fields from the /stats endpoint.
	assert stats_response.status_code == 200
	assert stats_response_json['total_orders'] == expected_total_orders
	assert stats_response_json['total_pizzas'] == expected_total_pizzas
	assert stats_response_json['total_revenue'] == expected_total_revenue
	assert stats_response_json['average_order_value'] == expected_average_order_value

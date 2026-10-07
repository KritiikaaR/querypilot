<!--
Business definitions: how people talk about this data, mapped to the schema.
app/agent.py loads this file into the system prompt under "Business definitions",
right after the schema. HTML comments like this one are stripped and not sent.
Facts about columns (formats, allowed values, what a row means) belong in the
-- comments in data/seed.py instead. Keep entries short and general.
-->
- "pizza" / "pizzas" with no size mentioned = a pizza type. Group by pizza_types.pizza_type_id and show pizza_types.name. Use pizzas.pizza_id (one type in one size) only when the question is about sizes.
- "sold" / "pizzas sold" / "units" = SUM(order_details.quantity), not COUNT(*).
- "pizzas in an order" = SUM(order_details.quantity) for that order_id.
- "revenue" / "sales" = SUM(order_details.quantity * pizzas.price).
- "order" = one row in orders (one ticket); "number of orders" = COUNT(DISTINCT order_id).
- "closed days" / "days with no orders" = dates in 2015 that have no rows in orders.

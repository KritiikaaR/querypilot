// Copy and settings that are easy to tweak without touching components.

export const GITHUB_REPO = "https://github.com/KritiikaaR/querypilot";
export const GITHUB_PROFILE = "https://github.com/KritiikaaR";

// Fill this in after running `python -m evals.run_eval` in backend/.
// While it's null, the landing page describes the test set without numbers.
export const EVAL_RESULTS = null;
// Example once you have it:
// export const EVAL_RESULTS = { model: "gpt-4o-mini", accuracy: 90.0, selfCorrected: 3, questions: 30 };

export const DATA_SOURCE = "https://mavenanalytics.io/data-playground/pizza-place-sales";

// Example questions shown as chips on the app's empty screen. Clicking one asks it.
export const SUGGESTIONS = [
  "What hour gets the most orders?",
  "Best-selling pizzas in July?",
  "Which day sold the most pizzas?",
  "Which pizzas have mushrooms?",
];

export const TABLE_NOTES = {
  orders: "When each order was placed: date and time",
  order_details: "Which pizzas were in each order, and how many",
  pizzas: "Every menu item: a pizza type in one size, with its price",
  pizza_types: "Pizza names, category, and ingredients",
};

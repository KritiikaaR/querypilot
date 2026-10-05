// Copy and settings that are easy to tweak without touching components.

export const GITHUB_REPO = "https://github.com/KritiikaaR/querypilot";
export const GITHUB_PROFILE = "https://github.com/KritiikaaR";

// Fill this in after running `python -m evals.run_eval` in backend/.
// While it's null, the landing page describes the test set without numbers.
export const EVAL_RESULTS = null;
// Example once you have it:
// export const EVAL_RESULTS = { model: "gpt-4o-mini", accuracy: 90.0, selfCorrected: 3, questions: 30 };

export const DATA_SOURCE = "https://mavenanalytics.io/data-playground/pizza-place-sales";

export const SUGGESTIONS = [
  {
    topic: "Sales",
    questions: [
      "What were the 5 best-selling pizzas by revenue in July?",
      "What was the total revenue each month?",
      "How much revenue did each pizza size bring in?",
    ],
  },
  {
    topic: "When people order",
    questions: [
      "What hour of the day gets the most orders?",
      "Which day of the week is busiest?",
      "On which date were the most pizzas sold?",
    ],
  },
  {
    topic: "The menu",
    questions: [
      "Which pizzas contain mushrooms?",
      "Which pizza brought in the least revenue?",
      "What is the average order value?",
    ],
  },
];

export const TABLE_NOTES = {
  orders: "When each order was placed: date and time",
  order_details: "Which pizzas were in each order, and how many",
  pizzas: "Every menu item: a pizza type in one size, with its price",
  pizza_types: "Pizza names, category, and ingredients",
};

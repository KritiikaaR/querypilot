// Copy and settings that are easy to tweak without touching components.

export const GITHUB_REPO = "https://github.com/KritiikaaR/querypilot";
export const GITHUB_PROFILE = "https://github.com/KritiikaaR";

// From `python -m evals.run_eval --repeat 3` in backend/ (accuracy = mean strict execution accuracy).
// Set to null to have the landing page describe the test set without numbers.
export const EVAL_RESULTS = { model: "gpt-4o-mini", accuracy: 96.7, selfCorrected: 0, questions: 30, runs: 3 };

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

// Copy and settings that are easy to tweak without touching components.

export const GITHUB_REPO = "https://github.com/KritiikaaR/querypilot";
export const GITHUB_PROFILE = "https://github.com/KritiikaaR";

// From `python -m evals.run_eval --repeat 3` in backend/ (accuracy = mean strict execution accuracy).
// Set to null to have the landing page describe the test set without numbers.
export const EVAL_RESULTS = { model: "gpt-4o-mini", accuracy: 96.7, selfCorrected: 0, questions: 30, runs: 3 };

export const DATA_SOURCE = "https://mavenanalytics.io/data-playground/pizza-place-sales";

// Example questions shown as chips on the app's empty screen. Clicking one asks it.
export const SUGGESTIONS = [
  "What hour gets the most orders?",
  "Best-selling pizzas in July?",
  "Which day sold the most pizzas?",
  "Which pizzas have mushrooms?",
];

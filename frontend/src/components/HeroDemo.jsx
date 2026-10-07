import { useState } from "react";

// A real question/answer pair from the pizza data, laid out like the app: what you
// type, the SQL it wrote (small, a peek under the hood), and what comes back. Each
// highlighted phrase in the question is linked (same color) to the SQL that implements it.
const LINKS = {
  top: { color: "amber", label: "5 best-selling" },
  revenue: { color: "blue", label: "revenue" },
  products: { color: "violet", label: "pizzas" },
  year: { color: "green", label: "in July" },
};
const ORDER = ["top", "products", "revenue", "year"];

const QUESTION = [
  ["What were the "],
  ["5 best-selling", "top"],
  [" "],
  ["pizzas", "products"],
  [" by "],
  ["revenue", "revenue"],
  [" "],
  ["in July", "year"],
  ["?"],
];

const SQL = [
  [["SELECT "], ["pt.name AS pizza", "products"], [","]],
  [["       ROUND("], ["SUM(od.quantity * p.price)", "revenue"], [", 2) AS revenue"]],
  [["FROM order_details od"]],
  [["JOIN pizzas p ON p.pizza_id = od.pizza_id"]],
  [["JOIN pizza_types pt ON pt.pizza_type_id = p.pizza_type_id", "products"]],
  [["JOIN orders o ON o.order_id = od.order_id"]],
  [["WHERE "], ["strftime('%m', o.date) = '07'", "year"]],
  [["GROUP BY pt.pizza_type_id", "products"]],
  [["ORDER BY revenue DESC", "top"]],
  [["LIMIT 5", "top"], [";"]],
];

const ANSWER = "The Thai Chicken Pizza was July's top seller at $4,073.75.";

const RESULT = [
  ["The Thai Chicken Pizza", 4073.75],
  ["The Barbecue Chicken Pizza", 3784.25],
  ["The Classic Deluxe Pizza", 3554.5],
  ["The Spicy Italian Pizza", 3459.0],
  ["The California Chicken Pizza", 3252.25],
];

export default function HeroDemo() {
  const [active, setActive] = useState(null);

  const mark = (text, link, key) => {
    if (!link) return <span key={key}>{text}</span>;
    const { color } = LINKS[link];
    const cls = ["hl", `hl-${color}`, `hl-seq-${ORDER.indexOf(link)}`,
      active === link ? "is-on" : "", active && active !== link ? "is-dim" : ""].join(" ");
    return (
      <span key={key} className={cls} onMouseEnter={() => setActive(link)} onMouseLeave={() => setActive(null)}>
        {text}
      </span>
    );
  };

  return (
    <figure className="demo" aria-label="Example: a question, the SQL QueryPilot wrote for it, and the answer">
      <div className="demo-ask">
        <p className="demo-question">
          {QUESTION.map(([t, link], i) =>
            link ? (
              <button key={i} type="button" className={`hl hl-${LINKS[link].color} hl-seq-${ORDER.indexOf(link)} ${active === link ? "is-on" : ""} ${active && active !== link ? "is-dim" : ""}`}
                      onMouseEnter={() => setActive(link)} onMouseLeave={() => setActive(null)}
                      onFocus={() => setActive(link)} onBlur={() => setActive(null)}>
                {t}
              </button>
            ) : (
              <span key={i}>{t}</span>
            )
          )}
        </p>
        <span className="demo-send" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 16 16"><path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </span>
      </div>

      <div className="demo-flow" aria-hidden="true" />

      <pre className="demo-sql" aria-label="Generated SQL">
        {SQL.map((line, i) => (
          <span className="demo-line" key={i}>
            {line.map(([t, link], j) => mark(t, link, j))}
            {"\n"}
          </span>
        ))}
      </pre>

      <div className="demo-flow" aria-hidden="true" />

      <div className="demo-out">
        <p className="demo-answer">{ANSWER}</p>
        <table className="demo-result">
          <thead>
            <tr><th>pizza</th><th className="num">revenue</th></tr>
          </thead>
          <tbody>
            {RESULT.map(([name, rev]) => (
              <tr key={name}>
                <td>{name}</td>
                <td className="num">${rev.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}

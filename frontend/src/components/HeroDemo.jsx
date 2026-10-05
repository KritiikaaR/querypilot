import { useState } from "react";

// A real question/answer pair from the pizza data. Each highlighted phrase in the
// question is linked (same color) to the part of the SQL that implements it.
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
  [["JOIN pizzas p ON p.pizza_id = od.pizza_id", "rule"]],
  [["JOIN pizza_types pt ON pt.pizza_type_id = p.pizza_type_id", "products"]],
  [["JOIN orders o ON o.order_id = od.order_id"]],
  [["WHERE "], ["strftime('%m', o.date) = '07'", "year"]],
  [["GROUP BY pt.pizza_type_id", "products"]],
  [["ORDER BY revenue DESC", "top"]],
  [["LIMIT 5", "top"], [";"]],
];

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
    if (link === "rule") {
      return (
        <span key={key} className={`hl hl-rule ${active === "rule" ? "is-on" : ""} ${active && active !== "rule" ? "is-dim" : ""}`}
              onMouseEnter={() => setActive("rule")} onMouseLeave={() => setActive(null)}>
          {text}
        </span>
      );
    }
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
      <div className="demo-q">
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
      </div>

      <pre className="demo-sql" aria-label="Generated SQL">
        {SQL.map((line, i) => (
          <span className="demo-line" key={i}>
            {line.map(([t, link], j) => mark(t, link, j))}
            {"\n"}
          </span>
        ))}
      </pre>

      <p className="demo-note">
        {active === "rule"
          ? "This join isn't in the question. A pizza's price depends on its size, and the schema notes say prices live in the pizzas table."
          : "Hover a highlighted phrase to see the SQL that answers it. The dotted line comes from notes about how the data works."}
      </p>

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
    </figure>
  );
}

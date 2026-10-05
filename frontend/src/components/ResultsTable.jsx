import { formatValue, humanizeColumn, isNumeric } from "../lib/format.js";

export default function ResultsTable({ result }) {
  if (result.rows.length === 0) return <p className="fine">Nothing in the data matched this question.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {result.columns.map((c, j) => (
              <th key={c} className={isNumeric(result.rows[0][j]) ? "num" : ""}>{humanizeColumn(c)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => (
            <tr key={i}>
              {row.map((v, j) => (
                <td key={j} className={isNumeric(v) ? "num" : ""}>
                  {formatValue(v, result.columns[j])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

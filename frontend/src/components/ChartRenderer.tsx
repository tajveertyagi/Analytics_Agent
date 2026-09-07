import { memo, useMemo } from "react";
import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";

const Plot = createPlotlyComponent(Plotly);

// plotly.js's own `responsive: true` handler is ResizeObserver-based and
// debounced -- that alone keeps charts sized to their container. We do NOT
// add react-plotly's `useResizeHandler` on top: it attaches an un-debounced
// window "resize" listener per chart that calls Plotly.Plots.resize()
// synchronously, so a burst of resize/DPI events (plugging in a monitor,
// screen-duplicate, presentation mode) freezes the main thread for seconds.
const PLOT_CONFIG: Partial<Plotly.Config> = { displayModeBar: false, responsive: true };
const PLOT_STYLE = { width: "100%", height: "360px" } as const;

function ChartRenderer({ figure }: { figure: Record<string, unknown> }) {
  const data = useMemo(() => (figure.data as Plotly.Data[]) ?? [], [figure]);
  const layout = useMemo<Partial<Plotly.Layout>>(() => {
    const base = (figure.layout as Partial<Plotly.Layout>) ?? {};
    return {
      ...base,
      autosize: true,
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: { color: "#e2e8f0" },
      margin: { t: 40, l: 50, r: 20, b: 40 },
    };
  }, [figure]);

  return (
    <div className="my-2 rounded-lg border border-slate-700 bg-slate-900 p-2">
      <Plot data={data} layout={layout} style={PLOT_STYLE} config={PLOT_CONFIG} />
    </div>
  );
}

// Charts never change once rendered (figure payload is stable), so keep them
// out of the re-render path that streaming tokens trigger on the parent.
export default memo(ChartRenderer, (a, b) => a.figure === b.figure);

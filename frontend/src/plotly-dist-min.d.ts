// plotly.js-dist-min ships no types; it's the same API surface as plotly.js,
// which @types/plotly.js describes.
declare module "plotly.js-dist-min" {
  export * from "plotly.js";
  import Plotly from "plotly.js";
  export default Plotly;
}

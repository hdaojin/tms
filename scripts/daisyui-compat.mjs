import daisyui from "daisyui";
import plugin from "tailwindcss/plugin";

export default plugin.withOptions(
  (options) => (api) => {
    daisyui(options).handler({
      ...api,
      addUtilities(styles) {
        // Tailwind hoists this scope, where Lightning CSS drops bare child selectors.
        // Remove after https://github.com/saadeghi/daisyui/issues/4851 is fixed upstream.
        const join = styles[".join"];
        const scope = join?.["@scope (&)"];
        if (!scope) {
          api.addUtilities(styles);
          return;
        }

        const scopeChildren = (rules) =>
          Object.fromEntries(
            Object.entries(rules).map(([selector, declarations]) => [
              selector.startsWith(">") ? `:scope ${selector}` : selector,
              declarations,
            ]),
          );

        const hover = "@media (hover: hover)";
        const scopedRules = scopeChildren(scope);
        if (scope[hover]) {
          scopedRules[hover] = scopeChildren(scope[hover]);
        }

        api.addUtilities({
          ...styles,
          ".join": { ...join, "@scope (&)": scopedRules },
        });
      },
    });
  },
  (options) => daisyui(options).config,
);

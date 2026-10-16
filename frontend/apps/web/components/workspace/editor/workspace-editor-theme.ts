// Betterleaf CodeMirror theme: light text on spruce ink, mirroring the
// landing page's "code window". Replaces the generic oneDark theme.

import { EditorView } from "@codemirror/view";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags as t } from "@lezer/highlight";

// Spruce tokens
const spruce = "#10281f";
const spruceDeep = "#16362b";
const lineDark = "#2b4f40";
const text = "#d9e6de";
const mutedText = "#7fa896"; // braces
const cmd = "#7fd1a6"; // commands
const sun = "#f2c14e"; // cursor / highlights

const blTheme = EditorView.theme(
  {
    "&": {
      backgroundColor: spruce,
      color: text,
      height: "100%",
      fontSize: "14px",
    },
    ".cm-scroller": {
      overflow: "auto",
      fontFamily:
        'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace',
      lineHeight: "1.6",
    },
    ".cm-content": {
      caretColor: sun,
      paddingLeft: "8px",
      paddingRight: "12px",
    },
    ".cm-cursor, .cm-dropCursor": {
      borderLeftColor: sun,
    },
    ".cm-gutters": {
      backgroundColor: spruce,
      color: "#5e8573",
      borderRight: `1px solid ${lineDark}`,
    },
    ".cm-lineNumbers .cm-gutterElement": {
      paddingLeft: "10px",
      paddingRight: "6px",
    },
    ".cm-activeLineGutter": {
      backgroundColor: spruceDeep,
      color: text,
    },
    ".cm-activeLine": {
      backgroundColor: spruceDeep,
    },
    ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": {
      backgroundColor: "#2b4f40 !important",
    },
    ".cm-searchMatch": {
      backgroundColor: `${sun} !important`,
      color: `${spruce} !important`,
      borderRadius: "2px",
      boxShadow: "0 0 0 1px #e8b63e",
    },
    ".cm-searchMatch.cm-searchMatch-selected": {
      backgroundColor: "#2e7d5b !important",
      color: "#fff !important",
      boxShadow: "0 0 0 2px #2e7d5b",
    },
    ".cm-matchingBracket, .cm-nonmatchingBracket": {
      color: text,
      backgroundColor: "#2b4f40",
    },
  },
  { dark: true },
);

const blHighlightStyle = HighlightStyle.define([
  { tag: t.comment, color: "#5e8573", fontStyle: "italic" },
  { tag: [t.keyword, t.operatorKeyword, t.modifier], color: cmd },
  { tag: [t.string, t.special(t.string)], color: "#a8d5bc" },
  { tag: [t.number, t.bool], color: sun },
  { tag: [t.name, t.variableName], color: text },
  {
    tag: [t.function(t.variableName), t.function(t.propertyName)],
    color: "#8fd3bd",
  },
  { tag: [t.labelName, t.definition(t.name)], color: "#c7e0d3" },
  { tag: [t.brace, t.bracket, t.paren], color: mutedText },
  { tag: t.invalid, color: "#f2c14e" },
]);

export const betterleafTheme = [blTheme, syntaxHighlighting(blHighlightStyle)];

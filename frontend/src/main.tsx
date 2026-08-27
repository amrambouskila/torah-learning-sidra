import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/App";
import "@/styles/tokens.css";
import "@/styles/base.css";
import "@/styles/rail.css";
import "@/styles/screens.css";

const root = document.getElementById("root");
if (root === null) throw new Error("no #root element in index.html");
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

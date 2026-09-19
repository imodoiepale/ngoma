"use client";

import { createContext } from "react";

// What every node on the canvas can read without it being copied into node data: estimates
// by node id, readiness by kind, the latest run manifest by node id, and the fan-out helper.
export const CanvasContext = createContext(null);

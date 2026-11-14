/** Numbers the components use, in one place. Colours and spacing live in tokens.css. */
export const chart = {
  /** viewBox width of a lane; height comes from --lane-h through preserveAspectRatio */
  width: 600,
  height: 52,
  /** robust z beyond this is drawn at the edge */
  zClip: 40,
  /** share of a lane's half-height the normal band takes */
  band: 0.3,
  /** minutes between axis labels */
  tick: 10,
};

export const schematic = {
  width: 1000,
  height: 150,
  machineW: 112,
  machineH: 64,
  /** gap between a machine and the conveyor under it */
  lift: 12,
  pad: 10,
  tagY: 34,
  typeY: 53,
  flagY: 20,
  corner: 3,
  conveyorY: 108,
  chevron: 5,
  arrowY: 136,
  arrowHead: 8,
};

export const motion = {
  draw: { duration: 0.9, ease: [0.3, 0, 0.2, 1] as const },
  swap: { duration: 0.2 },
};

export const skeletonRows = 4;
export const skeletonStep = 12;

export const pct = (x: number, digits = 1) => `${(x * 100).toFixed(digits)}%`;
export const int = (x: number) => x.toLocaleString("en-GB");

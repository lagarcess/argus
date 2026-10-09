import { copyFile, mkdir } from "node:fs/promises";

const source = new URL("../brand/cuadrao-lockup-light.svg", import.meta.url);
const destination = new URL("../public/cuadrao-site/", import.meta.url);
await mkdir(destination, { recursive: true });
await copyFile(source, new URL("cuadrao-lockup-light.svg", destination));

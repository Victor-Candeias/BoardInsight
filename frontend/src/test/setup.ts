import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// O servidor de destino é lento (Atom): dar margem às esperas assíncronas.
configure({ asyncUtilTimeout: 5000 });

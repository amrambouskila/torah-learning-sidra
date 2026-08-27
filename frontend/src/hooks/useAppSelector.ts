import { useSelector } from "react-redux";

import type { RootState } from "@/stores/store";

export const useAppSelector = useSelector.withTypes<RootState>();

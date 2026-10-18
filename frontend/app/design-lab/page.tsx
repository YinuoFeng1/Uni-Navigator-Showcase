import { notFound } from "next/navigation";
import { DesignLab } from "@/components/design-lab/DesignLab";
import { isDesignLabEnabled } from "@/lib/uiThemePolicy.mjs";

export default function DesignLabPage() {
  const enabled = isDesignLabEnabled({
    nodeEnv: process.env.NODE_ENV,
    studyMode: process.env.NEXT_PUBLIC_STUDY_MODE ?? "development",
  });
  if (!enabled) notFound();
  return <DesignLab />;
}

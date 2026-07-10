import type { Metadata } from "next";
import { SandboxWorkspace } from "@/components/action-control/SandboxWorkspace";

export const metadata: Metadata = {
  title: "Action Control sandbox — rollback-isolated payload governance",
  description: "Approve, commit, retry, and tamper with a synthetic customer draft without external effects.",
};

export default function ActionControlSandboxPage() {
  return <SandboxWorkspace />;
}

import { MerchantShell } from "@/components/merchant/Shell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <MerchantShell>{children}</MerchantShell>;
}

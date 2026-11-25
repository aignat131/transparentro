import { redirect } from "next/navigation";

// Licitațiile deschise fac acum parte din pagina de oportunități.
export default function TendersPage() {
  redirect("/oportunitati");
}

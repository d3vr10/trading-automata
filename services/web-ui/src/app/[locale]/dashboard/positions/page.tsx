"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { listPositions, type Position } from "@/lib/api";
import { TableSkeleton } from "@/components/skeletons";

export default function PositionsPage() {
  const t = useTranslations("positions");
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listPositions(true)
      .then(setPositions)
      .catch(() => setPositions([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>

      <div className="glass rounded-2xl overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-border/30 hover:bg-transparent">
              <TableHead className="text-muted-foreground/80">{t("table.symbol")}</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.strategy")}</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.bot")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("table.quantity")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("table.entryPrice")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("table.currentPrice")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("table.unrealizedPnl")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableSkeleton columns={7} rows={5} />
            ) : positions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-muted-foreground text-center py-8">
                  {t("noPositions")}
                </TableCell>
              </TableRow>
            ) : (
              positions.map((pos) => (
                <TableRow key={pos.id} className="border-border/20 hover:bg-accent/20">
                  <TableCell className="font-medium">{pos.symbol}</TableCell>
                  <TableCell className="text-muted-foreground">{pos.strategy}</TableCell>
                  <TableCell className="text-muted-foreground">{pos.bot_name || "-"}</TableCell>
                  <TableCell className="text-right">{pos.quantity}</TableCell>
                  <TableCell className="text-right">${pos.entry_price.toFixed(2)}</TableCell>
                  <TableCell className="text-right">
                    {pos.current_price !== null ? `$${pos.current_price.toFixed(2)}` : t("table.notAvailable")}
                  </TableCell>
                  <TableCell className={`text-right font-medium ${(pos.unrealized_pnl || 0) >= 0 ? "text-primary" : "text-destructive"}`}>
                    {pos.unrealized_pnl !== null ? `$${pos.unrealized_pnl.toFixed(2)}` : t("table.notAvailable")}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

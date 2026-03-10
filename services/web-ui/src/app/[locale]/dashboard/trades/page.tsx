"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { listTrades, type Trade } from "@/lib/api";
import { TableSkeleton } from "@/components/skeletons";

export default function TradesPage() {
  const t = useTranslations("trades");
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const limit = 25;

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const data = await listTrades({
          limit,
          offset,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
        });
        setTrades(data);
      } catch {
        setTrades([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [offset, dateFrom, dateTo]);

  function handleDateChange(type: "from" | "to", value: string) {
    setOffset(0);
    if (type === "from") setDateFrom(value);
    else setDateTo(value);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>

      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground">{t("filters.dateFrom")}</label>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => handleDateChange("from", e.target.value)}
            className="h-8 w-auto rounded-lg text-sm"
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground">{t("filters.dateTo")}</label>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => handleDateChange("to", e.target.value)}
            className="h-8 w-auto rounded-lg text-sm"
          />
        </div>
        {(dateFrom || dateTo) && (
          <Button
            variant="ghost"
            size="sm"
            className="rounded-lg h-8 text-xs"
            onClick={() => { setDateFrom(""); setDateTo(""); setOffset(0); }}
          >
            {t("filters.clear")}
          </Button>
        )}
      </div>

      <div className="glass rounded-2xl overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-border/30 hover:bg-transparent">
              <TableHead className="text-muted-foreground/80">{t("table.symbol")}</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.strategy")}</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.bot")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("table.entry")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("table.qty")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("table.exit")}</TableHead>
              <TableHead className="text-right text-muted-foreground/80">{t("table.pnl")}</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.result")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableSkeleton columns={8} rows={8} />
            ) : trades.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-muted-foreground text-center py-8">
                  {t("noTrades")}
                </TableCell>
              </TableRow>
            ) : (
              trades.map((trade) => (
                <TableRow key={trade.id} className="border-border/20 hover:bg-accent/20">
                  <TableCell className="font-medium">{trade.symbol}</TableCell>
                  <TableCell className="text-muted-foreground">{trade.strategy}</TableCell>
                  <TableCell className="text-muted-foreground">{trade.bot_name || "-"}</TableCell>
                  <TableCell className="text-right">${trade.entry_price.toFixed(2)}</TableCell>
                  <TableCell className="text-right">{trade.entry_quantity}</TableCell>
                  <TableCell className="text-right">
                    {trade.exit_price !== null ? `$${trade.exit_price.toFixed(2)}` : "-"}
                  </TableCell>
                  <TableCell className={`text-right font-medium ${(trade.net_pnl || 0) >= 0 ? "text-primary" : "text-destructive"}`}>
                    {trade.net_pnl !== null ? `$${trade.net_pnl.toFixed(2)}` : "-"}
                  </TableCell>
                  <TableCell>
                    {trade.is_winning_trade !== null ? (
                      <Badge
                        variant={trade.is_winning_trade ? "default" : "destructive"}
                        className={trade.is_winning_trade ? "bg-primary/20 text-primary border-primary/30" : ""}
                      >
                        {trade.is_winning_trade ? t("table.win") : t("table.loss")}
                      </Badge>
                    ) : (
                      <Badge variant="secondary">{t("table.open")}</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="rounded-lg"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - limit))}
        >
          {t("previous")}
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="rounded-lg"
          disabled={trades.length < limit}
          onClick={() => setOffset(offset + limit)}
        >
          {t("next")}
        </Button>
      </div>
    </div>
  );
}

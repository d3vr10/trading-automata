"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { listUsers, createUser, deleteUser, type User } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { TableSkeleton } from "@/components/skeletons";

export default function AdminUsersPage() {
  const t = useTranslations("admin.users");
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("user");
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    try {
      const data = await listUsers();
      setUsers(data);
    } catch {
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createUser({ username, password, email: email || undefined, role });
      toast.success(t("userCreated", { name: username }));
      setDialogOpen(false);
      setUsername("");
      setPassword("");
      setEmail("");
      setRole("user");
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(userId: number, name: string) {
    if (!confirm(t("confirmDelete", { name }))) return;
    try {
      await deleteUser(userId);
      toast.success(t("userDeleted", { name }));
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete user");
    }
  }

  if (currentUser && currentUser.role !== "root" && currentUser.role !== "admin") {
    return <div className="text-muted-foreground">{t("accessDenied")}</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-xl glow-accent"><Plus className="mr-2 h-4 w-4" /> {t("addUser")}</Button>
          </DialogTrigger>
          <DialogContent className="glass-strong border-border/30 rounded-2xl">
            <DialogHeader>
              <DialogTitle>{t("dialog.title")}</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">{t("dialog.username")}</Label>
                <Input value={username} onChange={(e) => setUsername(e.target.value)} required className="h-10 bg-input/50 border-border/50 rounded-xl" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">{t("dialog.password")}</Label>
                <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className="h-10 bg-input/50 border-border/50 rounded-xl" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">{t("dialog.email")}</Label>
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="h-10 bg-input/50 border-border/50 rounded-xl" />
              </div>
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">{t("dialog.role")}</Label>
                <select
                  className="flex h-10 w-full rounded-xl border border-border/50 bg-input/50 px-3 py-1 text-sm"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                >
                  <option value="user">{t("dialog.user")}</option>
                  {currentUser?.role === "root" && <option value="admin">{t("dialog.admin")}</option>}
                </select>
              </div>
              <Button type="submit" className="w-full rounded-xl glow-accent" disabled={submitting}>
                {submitting ? t("dialog.creating") : t("dialog.create")}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="glass rounded-2xl overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-border/30 hover:bg-transparent">
              <TableHead className="text-muted-foreground/80">ID</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.username")}</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.email")}</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.role")}</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.status")}</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableSkeleton columns={6} rows={4} />
            ) : (
              users.map((u) => (
                <TableRow key={u.id} className="border-border/20 hover:bg-accent/20">
                  <TableCell className="text-muted-foreground">{u.id}</TableCell>
                  <TableCell className="font-medium">{u.username}</TableCell>
                  <TableCell className="text-muted-foreground">{u.email || "-"}</TableCell>
                  <TableCell>
                    <Badge
                      variant={u.role === "root" ? "default" : u.role === "admin" ? "secondary" : "outline"}
                      className={u.role === "root" ? "bg-primary/20 text-primary border-primary/30" : ""}
                    >
                      {u.role}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={u.is_active ? "default" : "destructive"}
                      className={u.is_active ? "bg-primary/20 text-primary border-primary/30" : ""}
                    >
                      {u.is_active ? t("table.active") : t("table.inactive")}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {u.role !== "root" && currentUser?.role === "root" && (
                      <Button variant="ghost" size="sm" className="rounded-lg hover:text-destructive" onClick={() => handleDelete(u.id, u.username)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
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

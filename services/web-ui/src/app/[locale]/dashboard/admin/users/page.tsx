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
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { listUsers, createUser, deleteUser, updateUser, type User } from "@/lib/api";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { TableSkeleton } from "@/components/skeletons";

export default function AdminUsersPage() {
  const t = useTranslations("admin.users");
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  // Delete confirmation state
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Create form
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("user");
  const [submitting, setSubmitting] = useState(false);

  // Edit form
  const [editEmail, setEditEmail] = useState("");
  const [editRole, setEditRole] = useState("user");
  const [editSubmitting, setEditSubmitting] = useState(false);

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
      setCreateOpen(false);
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

  function openEdit(u: User) {
    setEditingUser(u);
    setEditEmail(u.email || "");
    setEditRole(u.role);
    setEditOpen(true);
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editingUser) return;
    setEditSubmitting(true);
    try {
      await updateUser(editingUser.id, { email: editEmail || undefined, role: editRole });
      toast.success(t("userUpdated", { name: editingUser.username }));
      setEditOpen(false);
      setEditingUser(null);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update user");
    } finally {
      setEditSubmitting(false);
    }
  }

  async function handleToggleActive(u: User) {
    try {
      await updateUser(u.id, { is_active: !u.is_active });
      setUsers((prev) => prev.map((x) => x.id === u.id ? { ...x, is_active: !x.is_active } : x));
    } catch {
      toast.error(t("toggleActiveFailed"));
    }
  }

  async function handleDelete(userId: number, name: string) {
    setDeleting(true);
    try {
      await deleteUser(userId);
      toast.success(t("userDeleted", { name }));
      setSelected((prev) => { const next = new Set(prev); next.delete(userId); return next; });
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete user");
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
    }
  }

  async function handleBulkDelete() {
    setDeleting(true);
    try {
      await Promise.all(Array.from(selected).map((id) => deleteUser(id)));
      toast.success(t("usersDeleted", { count: selected.size }));
      setSelected(new Set());
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete users");
    } finally {
      setDeleting(false);
      setBulkDeleteOpen(false);
    }
  }

  // Only non-root users that the current user can manage
  const selectableUsers = users.filter((u) => u.role !== "root");
  const allSelected = selectableUsers.length > 0 && selectableUsers.every((u) => selected.has(u.id));

  function toggleAll() {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(selectableUsers.map((u) => u.id)));
    }
  }

  function toggleOne(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  if (currentUser && currentUser.role !== "root" && currentUser.role !== "admin") {
    return <div className="text-muted-foreground">{t("accessDenied")}</div>;
  }

  const isRoot = currentUser?.role === "root";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          {selected.size > 0 && (
            <Badge variant="secondary" className="text-xs">
              {t("selected", { count: selected.size })}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {selected.size > 0 && isRoot && (
            <Button
              variant="destructive"
              className="rounded-xl"
              onClick={() => setBulkDeleteOpen(true)}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {t("deleteSelected", { count: selected.size })}
            </Button>
          )}
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
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
                  <Select value={role} onValueChange={setRole}>
                    <SelectTrigger className="h-10 w-full rounded-xl border-border/50 bg-input/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="glass-strong border-border/30 rounded-xl">
                      <SelectItem value="user">{t("dialog.user")}</SelectItem>
                      {isRoot && <SelectItem value="admin">{t("dialog.admin")}</SelectItem>}
                    </SelectContent>
                  </Select>
                </div>
                <Button type="submit" className="w-full rounded-xl glow-accent" disabled={submitting}>
                  {submitting ? t("dialog.creating") : t("dialog.create")}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="glass rounded-2xl overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-border/30 hover:bg-transparent">
              {isRoot && (
                <TableHead className="w-10">
                  <Checkbox checked={allSelected} onCheckedChange={toggleAll} />
                </TableHead>
              )}
              <TableHead className="text-muted-foreground/80">ID</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.username")}</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.email")}</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.role")}</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.status")}</TableHead>
              <TableHead className="text-muted-foreground/80">{t("table.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableSkeleton columns={isRoot ? 7 : 6} rows={4} />
            ) : (
              users.map((u) => (
                <TableRow key={u.id} className={`border-border/20 hover:bg-accent/20 ${selected.has(u.id) ? "bg-accent/10" : ""}`}>
                  {isRoot && (
                    <TableCell>
                      {u.role !== "root" ? (
                        <Checkbox checked={selected.has(u.id)} onCheckedChange={() => toggleOne(u.id)} />
                      ) : null}
                    </TableCell>
                  )}
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
                    {u.role !== "root" && isRoot ? (
                      <Switch checked={u.is_active} onCheckedChange={() => handleToggleActive(u)} />
                    ) : (
                      <Badge
                        variant={u.is_active ? "default" : "destructive"}
                        className={u.is_active ? "bg-primary/20 text-primary border-primary/30" : ""}
                      >
                        {u.is_active ? t("table.active") : t("table.inactive")}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {u.role !== "root" && isRoot && (
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="sm" className="rounded-lg hover:text-primary" onClick={() => openEdit(u)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" className="rounded-lg hover:text-destructive" onClick={() => setDeleteTarget({ id: u.id, name: u.username })}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Edit User Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="glass-strong border-border/30 rounded-2xl">
          <DialogHeader>
            <DialogTitle>{t("dialog.editTitle")}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEdit} className="space-y-4">
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">{t("dialog.username")}</Label>
              <Input value={editingUser?.username || ""} disabled className="h-10 bg-input/50 border-border/50 rounded-xl opacity-60" />
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">{t("dialog.editEmail")}</Label>
              <Input type="email" value={editEmail} onChange={(e) => setEditEmail(e.target.value)} className="h-10 bg-input/50 border-border/50 rounded-xl" />
            </div>
            <div className="space-y-2">
              <Label className="text-sm text-muted-foreground">{t("dialog.role")}</Label>
              <Select value={editRole} onValueChange={setEditRole}>
                <SelectTrigger className="h-10 w-full rounded-xl border-border/50 bg-input/50">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="glass-strong border-border/30 rounded-xl">
                  <SelectItem value="user">{t("dialog.user")}</SelectItem>
                  <SelectItem value="admin">{t("dialog.admin")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-2">
              <Button type="submit" className="flex-1 rounded-xl glow-accent" disabled={editSubmitting}>
                {editSubmitting ? t("dialog.saving") : t("dialog.save")}
              </Button>
              <Button type="button" variant="outline" className="rounded-xl" onClick={() => setEditOpen(false)}>
                {t("dialog.cancel")}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Single Delete Confirmation */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}>
        <AlertDialogContent className="glass-strong border-border/30 rounded-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle>{t("dialog.deleteConfirmTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget && t("confirmDelete", { name: deleteTarget.name })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-xl">{t("dialog.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              className="rounded-xl bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleting}
              onClick={() => deleteTarget && handleDelete(deleteTarget.id, deleteTarget.name)}
            >
              {deleting ? t("dialog.deleting") : t("dialog.deleteBtn")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk Delete Confirmation */}
      <AlertDialog open={bulkDeleteOpen} onOpenChange={setBulkDeleteOpen}>
        <AlertDialogContent className="glass-strong border-border/30 rounded-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle>{t("dialog.deleteConfirmTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("confirmDeleteMultiple", { count: selected.size })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-xl">{t("dialog.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              className="rounded-xl bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleting}
              onClick={handleBulkDelete}
            >
              {deleting ? t("dialog.deleting") : t("dialog.deleteBtn")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

"use client";

import { useState, type ReactNode } from "react";
import { Pencil, Plus } from "lucide-react";
import { errorText, patch, post } from "@/lib/api";
import { Row } from "@/lib/types";
import { Button, Empty, ErrorNote, Field, Modal, useToast } from "./ui";

export type FormField = {
  name: string;
  label: string;
  type?:
    | "text"
    | "textarea"
    | "number"
    | "money"
    | "email"
    | "password"
    | "select"
    | "multiselect"
    | "checkbox"
    | "time"
    | "datetime-local"
    | "color";
  required?: boolean;
  hint?: string;
  options?: { value: string; label: string }[];
  defaultValue?: unknown;
  min?: number;
  max?: number;
  onlyCreate?: boolean;
};
export type Column = {
  key: string;
  label: string;
  render?: (row: Row) => ReactNode;
};
type ResourceProps = {
  title: string;
  description: string;
  singular: string;
  resource: string;
  rows: Row[];
  fields: FormField[];
  columns: Column[];
  canEdit: boolean;
  onSaved: () => void;
  search?: string;
  extra?: ReactNode;
  canEditRow?: (row: Row) => boolean;
};

export function ResourceManager({
  title,
  description,
  singular,
  resource,
  rows,
  fields,
  columns,
  canEdit,
  onSaved,
  search = "",
  extra,
  canEditRow,
}: ResourceProps) {
  const [edit, setEdit] = useState<Row | null | undefined>(undefined);
  const visible = rows.filter(
    (r) =>
      !search ||
      Object.values(r).some((v) =>
        String(v).toLowerCase().includes(search.toLowerCase()),
      ),
  );
  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>
            {title}
            <span className="count-label">{rows.length}</span>
          </h2>
          <p>{description}</p>
        </div>
        {canEdit && (
          <Button onClick={() => setEdit(null)}>
            <Plus size={16} />
            {singular}
          </Button>
        )}
      </div>
      {extra}
      <div className="panel table-panel">
        {visible.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {columns.map((c) => (
                    <th key={c.key}>{c.label}</th>
                  ))}
                  {canEdit && (
                    <th>
                      <span className="sr-only">Действия</span>
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr key={row.id}>
                    {columns.map((c) => (
                      <td key={c.key}>
                        {c.render ? c.render(row) : String(row[c.key] ?? "—")}
                      </td>
                    ))}
                    {canEdit && (
                      <td className="table-actions">
                        {(!canEditRow || canEditRow(row)) && (
                          <button
                            className="icon-btn"
                            title="Изменить"
                            aria-label={`Изменить ${row.name || row.title || "запись"}`}
                            onClick={() => setEdit(row)}
                          >
                            <Pencil size={16} />
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title={search ? "Ничего не найдено" : "Пока нет данных"}
            text={
              search
                ? "Попробуйте изменить поисковый запрос."
                : `Создайте первую запись в разделе «${title}».`
            }
          />
        )}
      </div>
      <Modal
        open={edit !== undefined}
        title={edit ? "Изменить запись" : singular}
        onClose={() => setEdit(undefined)}
      >
        <RecordForm
          resource={resource}
          fields={fields}
          initial={edit || undefined}
          onSaved={() => {
            setEdit(undefined);
            onSaved();
          }}
          onCancel={() => setEdit(undefined)}
        />
      </Modal>
    </>
  );
}

export function RecordForm({
  resource,
  fields,
  initial,
  onSaved,
  onCancel,
  endpoint,
  method,
}: {
  resource?: string;
  fields: FormField[];
  initial?: Row;
  onSaved: () => void;
  onCancel: () => void;
  endpoint?: string;
  method?: "POST" | "PATCH";
}) {
  const activeFields = fields.filter((f) => !(f.onlyCreate && initial));
  const [values, setValues] = useState<Record<string, unknown>>(() =>
    Object.fromEntries(
      activeFields.map((f) => {
        let value =
          initial?.[f.name] ??
          f.defaultValue ??
          (f.type === "checkbox" ? true : f.type === "multiselect" ? [] : "");
        if (f.type === "money") value = Number(value || 0) / 100;
        if (f.type === "datetime-local" && value) {
          const date = new Date(String(value));
          value = new Date(date.getTime() + 3 * 60 * 60000)
            .toISOString()
            .slice(0, 16);
        }
        return [f.name, value];
      }),
    ),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();
  function set(name: string, value: unknown) {
    setValues((v) => ({ ...v, [name]: value }));
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const payload: Record<string, unknown> = {};
    for (const field of activeFields) {
      let value = values[field.name];
      if (field.type === "password" && !value && initial) continue;
      if (field.type === "money") value = Math.round(Number(value) * 100);
      if (field.type === "number") value = Number(value);
      if (field.type === "datetime-local" && value)
        value = new Date(`${value}:00+03:00`).toISOString();
      if (
        ["datetime-local", "time"].includes(field.type || "") &&
        value === "" &&
        !field.required
      )
        value = null;
      if (field.type === "select" && value === "" && !field.required)
        value = null;
      payload[field.name] = value;
    }
    const path =
      endpoint || `/admin/${resource}${initial ? `/${initial.id}` : ""}`;
    try {
      if ((method || (initial ? "PATCH" : "POST")) === "PATCH")
        await patch(path, payload);
      else await post(path, payload);
      toast("Изменения сохранены");
      onSaved();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="record-form">
      {activeFields.map((f) =>
        f.type === "checkbox" ? (
          <label className="checkbox-field" key={f.name}>
            <input
              type="checkbox"
              checked={Boolean(values[f.name])}
              onChange={(e) => set(f.name, e.target.checked)}
            />
            <span>
              {f.label}
              {f.hint && <small>{f.hint}</small>}
            </span>
          </label>
        ) : f.type === "multiselect" ? (
          <div className="field" key={f.name}>
            <span>{f.label}</span>
            <div className="multi-checks">
              {f.options?.map((o) => (
                <label className="checkbox-field" key={o.value}>
                  <input
                    type="checkbox"
                    checked={((values[f.name] as string[]) || []).includes(
                      o.value,
                    )}
                    onChange={(e) => {
                      const selected = (values[f.name] as string[]) || [];
                      set(
                        f.name,
                        e.target.checked
                          ? [...selected, o.value]
                          : selected.filter((v) => v !== o.value),
                      );
                    }}
                  />
                  <span>{o.label}</span>
                </label>
              ))}
            </div>
          </div>
        ) : (
          <Field label={f.label} hint={f.hint} key={f.name}>
            {f.type === "textarea" ? (
              <textarea
                rows={4}
                required={f.required}
                value={String(values[f.name] ?? "")}
                onChange={(e) => set(f.name, e.target.value)}
                maxLength={10000}
              />
            ) : f.type === "select" ? (
              <select
                required={f.required}
                value={String(values[f.name] ?? "")}
                onChange={(e) => set(f.name, e.target.value)}
              >
                <option value="">
                  {f.required ? "Выберите значение" : "Не назначено"}
                </option>
                {f.options?.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={f.type === "money" ? "number" : f.type || "text"}
                required={f.required || (f.type === "password" && !initial)}
                value={String(values[f.name] ?? "")}
                onChange={(e) => set(f.name, e.target.value)}
                step={
                  f.type === "money"
                    ? "0.01"
                    : f.type === "number"
                      ? "1"
                      : undefined
                }
                min={f.min}
                max={f.max}
                minLength={f.type === "password" ? 12 : undefined}
                autoComplete={
                  f.type === "password" ? "new-password" : undefined
                }
                maxLength={f.type === "text" || !f.type ? 500 : undefined}
              />
            )}
          </Field>
        ),
      )}
      <ErrorNote message={error} />
      <div className="modal-actions">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Отмена
        </Button>
        <Button type="submit" loading={busy}>
          Сохранить
        </Button>
      </div>
    </form>
  );
}

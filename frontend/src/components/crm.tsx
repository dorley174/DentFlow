"use client";
import { useState } from "react";
import { ArrowUpRight, GripVertical, Plus } from "lucide-react";
import { Bootstrap, Lead, Row } from "@/lib/types";
import { currency, stages } from "@/lib/format";
import { errorText, patch } from "@/lib/api";
import { Avatar, Badge, Button, Modal, useToast } from "./ui";
import { FormField, RecordForm } from "./resource-manager";

export function CRM({
  data,
  onSaved,
  search,
}: {
  data: Bootstrap;
  onSaved: () => void;
  search: string;
}) {
  const [edit, setEdit] = useState<Lead | null | undefined>(undefined);
  const [dragging, setDragging] = useState("");
  const [busy, setBusy] = useState("");
  const toast = useToast();
  const leads = data.leads.filter((l) =>
    `${l.title} ${l.patient_name} ${l.summary}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const fields: FormField[] = [
    { name: "title", label: "Название обращения", required: true },
    {
      name: "patient_id",
      label: "Пациент",
      type: "select",
      options: data.patients.map((p) => ({ value: p.id, label: p.name })),
      onlyCreate: true,
    },
    {
      name: "stage",
      label: "Стадия",
      type: "select",
      required: true,
      defaultValue: "Новое обращение",
      options: stages.map((s) => ({ value: s, label: s })),
    },
    {
      name: "assigned_to",
      label: "Ответственный",
      type: "select",
      options: data.staff.map((s) => ({ value: s.id, label: String(s.name) })),
    },
    { name: "summary", label: "Краткое содержание", type: "textarea" },
    {
      name: "amount_kopecks",
      label: "Сумма, ₽",
      type: "money",
      min: 0,
      defaultValue: 0,
    },
  ];
  async function move(id: string, stage: string) {
    if (!id || busy) return;
    setBusy(id);
    try {
      await patch(`/admin/leads/${id}`, { stage });
      onSaved();
      toast(`Стадия: ${stage}`);
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy("");
      setDragging("");
    }
  }
  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>
            Воронка обращений{" "}
            <span className="count-label">{data.leads.length}</span>
          </h2>
          <p>Перемещайте карточки или выбирайте стадию в меню обращения.</p>
        </div>
        <Button onClick={() => setEdit(null)}>
          <Plus size={17} />
          Новое обращение
        </Button>
      </div>
      <div className="crm-summary">
        <span>
          В работе{" "}
          <strong>
            {
              data.leads.filter(
                (l) => !["Завершено", "Потерян"].includes(l.stage),
              ).length
            }
          </strong>
        </span>
        <span>
          Сумма обращений{" "}
          <strong>
            {currency(
              data.leads
                .filter((l) => l.stage !== "Потерян")
                .reduce((sum, l) => sum + l.amount_kopecks, 0),
            )}
          </strong>
        </span>
        <Badge tone="blue">Данные из вашей CRM</Badge>
      </div>
      <div className="kanban-board">
        {stages.map((stage, index) => {
          const items = leads.filter((l) => l.stage === stage);
          return (
            <section
              key={stage}
              className={`kanban-column ${dragging ? "is-target" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
              }}
              onDrop={(e) => {
                e.preventDefault();
                move(e.dataTransfer.getData("text/plain"), stage);
              }}
            >
              <h3>
                <span className={`stage-dot stage-${index % 5}`} />
                {stage}
                <small>{items.length}</small>
              </h3>
              <div className="kanban-cards">
                {items.map((l) => (
                  <article
                    key={l.id}
                    className={`lead-card ${busy === l.id ? "is-saving" : ""}`}
                    draggable={!busy}
                    onDragStart={(e) => {
                      e.dataTransfer.setData("text/plain", l.id);
                      setDragging(l.id);
                    }}
                    onDragEnd={() => setDragging("")}
                  >
                    <div className="lead-source">
                      <Badge>
                        {l.source === "telegram"
                          ? "Telegram"
                          : l.source === "web"
                            ? "Веб-чат"
                            : l.source === "manual"
                              ? "Вручную"
                              : "Демо"}
                      </Badge>
                      <GripVertical size={15} />
                    </div>
                    <button className="lead-title" onClick={() => setEdit(l)}>
                      {l.title}
                      <ArrowUpRight size={14} />
                    </button>
                    <div className="lead-patient">
                      <Avatar name={l.patient_name || "Пациент"} small />
                      <span>{l.patient_name || "Без привязки к пациенту"}</span>
                    </div>
                    {l.summary && <p>{l.summary}</p>}
                    <div className="lead-bottom">
                      <strong>{currency(l.amount_kopecks)}</strong>
                      <span>
                        {data.staff.find((s) => s.id === l.assigned_to)?.name
                          ? String(
                              data.staff.find((s) => s.id === l.assigned_to)
                                ?.name,
                            ).split(" ")[0]
                          : "Не назначен"}
                      </span>
                    </div>
                    <select
                      aria-label={`Стадия: ${l.title}`}
                      value={l.stage}
                      disabled={Boolean(busy)}
                      onChange={(e) => move(l.id, e.target.value)}
                    >
                      {stages.map((s) => (
                        <option value={s} key={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </article>
                ))}
                {!items.length && (
                  <div className="kanban-empty">Нет обращений</div>
                )}
              </div>
            </section>
          );
        })}
      </div>
      <Modal
        open={edit !== undefined}
        onClose={() => setEdit(undefined)}
        title={edit ? "Карточка обращения" : "Новое обращение"}
      >
        <RecordForm
          resource="leads"
          fields={fields}
          initial={edit as Row | undefined}
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

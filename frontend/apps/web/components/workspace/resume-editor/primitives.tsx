"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVerticalIcon } from "lucide-react";
import { moveItem, type ResumeData } from "@/lib/resume-data";

/* ---------------------------------------------------------------- context */

export interface EditorApi {
  edit: (update: (draft: ResumeData) => ResumeData) => void;
  /** Apply a removal and offer an Undo for it. */
  removeWithUndo: (
    label: string,
    update: (draft: ResumeData) => ResumeData,
  ) => void;
}

const EditorContext = createContext<EditorApi | null>(null);
export const EditorProvider = EditorContext.Provider;

export function useEditor(): EditorApi {
  const api = useContext(EditorContext);
  if (!api) throw new Error("useEditor must be used inside <EditorProvider>");
  return api;
}

/* ----------------------------------------------------------------- fields */

interface FieldProps {
  label: string;
  value: string | null | undefined;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
  inputMode?: "email" | "tel" | "url" | "text";
  className?: string;
  large?: boolean;
}

export function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  inputMode,
  className = "",
  large,
}: FieldProps) {
  const id = useId();
  return (
    <div className={`re-field ${className}`}>
      <label htmlFor={id} className="re-label">
        {label}
      </label>
      <input
        id={id}
        type={type}
        inputMode={inputMode}
        className={`re-input${large ? " re-input-large" : ""}`}
        value={value ?? ""}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={type === "text"}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

/** A textarea that grows with its content. */
export function AutoTextarea({
  value,
  className = "",
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { value: string }) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const fit = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, []);
  useLayoutEffect(fit, [value, fit]);
  // Re-measure when the pane is resized, since wrapping changes the height.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let width = el.clientWidth;
    const observer = new ResizeObserver(() => {
      if (el.clientWidth !== width) {
        width = el.clientWidth;
        fit();
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [fit]);
  return (
    <textarea
      ref={ref}
      rows={1}
      value={value}
      className={`re-input re-textarea ${className}`}
      {...rest}
    />
  );
}

export function IconButton({
  label,
  onClick,
  children,
  className = "",
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      className={`re-icon-btn ${className}`}
      aria-label={label}
      title={label}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

/* --------------------------------------------------------- sortable lists */

function SortableRow({
  id,
  className,
  children,
}: {
  id: string;
  className?: string;
  children: (handle: ReactNode) => ReactNode;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });
  const handle = (
    <button
      type="button"
      ref={setActivatorNodeRef}
      className="re-grip"
      aria-label="Drag to reorder. Space to pick up, arrow keys to move."
      title="Drag to reorder"
      {...attributes}
      {...listeners}
    >
      <GripVerticalIcon className="size-4" aria-hidden="true" />
    </button>
  );
  return (
    <div
      ref={setNodeRef}
      className={`${className ?? ""}${isDragging ? " is-dragging" : ""}`}
      style={{
        transform: CSS.Transform.toString(
          transform ? { ...transform, x: 0, scaleX: 1, scaleY: 1 } : null,
        ),
        transition,
      }}
    >
      {children(handle)}
    </div>
  );
}

/** Vertical drag-and-drop list (pointer, touch and keyboard). */
export function SortableList<T extends { id: string }>({
  items,
  onReorder,
  rowClassName,
  renderRow,
}: {
  items: T[];
  onReorder: (next: T[]) => void;
  rowClassName?: string;
  renderRow: (item: T, index: number, handle: ReactNode) => ReactNode;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const from = items.findIndex((i) => i.id === active.id);
    const to = items.findIndex((i) => i.id === over.id);
    onReorder(moveItem(items, from, to));
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={onDragEnd}
    >
      <SortableContext
        items={items.map((i) => i.id)}
        strategy={verticalListSortingStrategy}
      >
        {items.map((item, index) => (
          <SortableRow key={item.id} id={item.id} className={rowClassName}>
            {(handle) => renderRow(item, index, handle)}
          </SortableRow>
        ))}
      </SortableContext>
    </DndContext>
  );
}

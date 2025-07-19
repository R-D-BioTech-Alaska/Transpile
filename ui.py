#!/usr/bin/env python3
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from builder import CircuitBuilder
from backend import BackendManager
from analyzer import analyze_transpile, default_pass_manager
from reporting import ReportGenerator


class QTranspileApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Quantum Transpile Suite")
        self.geometry("1200x800")

        self.backend_mgr = BackendManager()
        self.builder = CircuitBuilder()
        self.selected_circuit = None
        self.analysis_data = None

        self._create_widgets()

    def _create_widgets(self):
        tab = ttk.Notebook(self)
        tab.pack(fill='both', expand=True)

        # Builder Tab
        frame_b = ttk.Frame(tab)
        tab.add(frame_b, text='Circuit Builder')
        self._build_builder_tab(frame_b)

        # Analyzer Tab
        frame_a = ttk.Frame(tab)
        tab.add(frame_a, text='Analyzer')
        self._build_analyzer_tab(frame_a)

        # Reporting Tab
        frame_r = ttk.Frame(tab)
        tab.add(frame_r, text='Reporting')
        self._build_reporting_tab(frame_r)

    def _build_builder_tab(self, parent):
        frm = ttk.Frame(parent, padding=10)
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text="Circuit Name:").grid(row=0, column=0, sticky='w')
        self.circ_name_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.circ_name_var, width=30).grid(row=0, column=1)

        ttk.Button(frm, text="New Bell (2q)", command=lambda: self._add_sample("Bell", 2)).grid(row=1, column=0)
        ttk.Button(frm, text="New GHZ (3q)", command=lambda: self._add_sample("GHZ", 3)).grid(row=1, column=1)
        ttk.Button(frm, text="Load QASM", command=self._load_qasm).grid(row=1, column=2)
        ttk.Button(frm, text="Save QASM", command=self._save_qasm).grid(row=1, column=3)

        ttk.Label(frm, text="Circuits:").grid(row=2, column=0, sticky='nw')
        self.circ_list = tk.Listbox(frm, height=8)
        self.circ_list.grid(row=3, column=0, columnspan=4, sticky='we')
        self.circ_list.bind('<<ListboxSelect>>', lambda e: self._select_circuit())

        self.circ_display = tk.Text(frm, height=20)
        self.circ_display.grid(row=4, column=0, columnspan=4, sticky='nsew')
        frm.rowconfigure(4, weight=1)
        frm.columnconfigure(3, weight=1)

    def _build_analyzer_tab(self, parent):
        frm = ttk.Frame(parent, padding=10)
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text="Backend:").grid(row=0, column=0, sticky='w')
        self.backend_var = tk.StringVar()
        backends = list(self.backend_mgr.backends.keys())
        ttk.Combobox(frm, textvariable=self.backend_var, values=backends, state='readonly').grid(row=0, column=1)
        self.backend_var.set(backends[0])

        ttk.Label(frm, text="Optimize Levels:").grid(row=1, column=0, sticky='w')
        self.levels_var = tk.StringVar(value="0,1,2,3")
        ttk.Entry(frm, textvariable=self.levels_var, width=20).grid(row=1, column=1)

        ttk.Button(frm, text="Run Analysis", command=self._start_analysis).grid(row=0, column=2, rowspan=2, padx=10)

        cols = ('Level', 'Fidelity', 'Depth', 'Size', 'Ops')
        self.tree = ttk.Treeview(frm, columns=cols, show='headings')
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor='center')
        self.tree.grid(row=2, column=0, columnspan=3, sticky='nsew')
        frm.rowconfigure(2, weight=1)
        frm.columnconfigure(2, weight=1)

    def _build_reporting_tab(self, parent):
        frm = ttk.Frame(parent, padding=10)
        frm.pack(fill='both', expand=True)

        ttk.Button(frm, text="Save CSV", command=self._save_csv).grid(row=0, column=0, padx=5)
        ttk.Button(frm, text="Save JSON", command=self._save_json).grid(row=0, column=1, padx=5)
        ttk.Button(frm, text="Plot Metrics", command=self._plot_metrics).grid(row=0, column=2, padx=5)
        ttk.Button(frm, text="Plot Ops", command=self._plot_ops).grid(row=0, column=3, padx=5)

    def _add_sample(self, name, qubits):
        qc = QuantumCircuit(qubits)
        qc.h(0)
        for i in range(qubits - 1):
            qc.cx(i, i+1)
        qc.save_statevector()
        label = f"{name} #{len(self.builder._qc.qubits)+1}"
        self.builder.add_qubits(0)  # sync internal state
        self.builder._qc = qc
        self.builder.name = label
        self._refresh_list()

    def _load_qasm(self):
        path = filedialog.askopenfilename(filetypes=[("QASM Files", "*.qasm")])
        if path:
            qc = self.builder.load_qasm(path)
            self._refresh_list()

    def _save_qasm(self):
        sel = self._current_selection()
        if not sel:
            messagebox.showwarning("No selection", "Choose a circuit first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".qasm")
        if path:
            self.builder.save_qasm(path)

    def _select_circuit(self):
        sel = self._current_selection()
        if sel:
            qc = self.builder.get_circuit()
            self.circ_display.delete("1.0", tk.END)
            self.circ_display.insert(tk.END, qc.draw(output="text"))

    def _refresh_list(self):
        self.circ_list.delete(0, tk.END)
        if self.builder._qc:
            self.circ_list.insert(tk.END, self.builder.name)

    def _current_selection(self):
        sel = self.circ_list.curselection()
        return self.circ_list.get(sel) if sel else None

    def _start_analysis(self):
        if not self.builder._qc:
            messagebox.showwarning("No circuit", "Build or load a circuit first.")
            return
        try:
            levels = list(map(int, self.levels_var.get().split(',')))
        except:
            messagebox.showerror("Invalid input", "Enter levels as 0,1,2")
            return

        backend = self.backend_mgr.set_backend(self.backend_var.get())
        qc = self.builder.get_circuit()
        self.tree.delete(*self.tree.get_children())

        def task():
            results = analyze_transpile(qc, backend, levels, default_pass_manager(backend.configuration().basis_gates))
            self.analysis_data = results
            for r in results:
                self.tree.insert("", tk.END, values=(
                    r['level'], f"{r['fidelity']:.6f}", r['depth'], r['size'], str(r['ops'])
                ))

        threading.Thread(target=task, daemon=True).start()

    def _save_csv(self):
        if not self.analysis_data:
            messagebox.showwarning("No data", "Run analysis first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv")
        if path:
            ReportGenerator(self.analysis_data).to_csv(path)

    def _save_json(self):
        if not self.analysis_data:
            messagebox.showwarning("No data", "Run analysis first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if path:
            ReportGenerator(self.analysis_data).to_json(path)

    def _plot_metrics(self):
        if not self.analysis_data:
            messagebox.showwarning("No data", "Run analysis first.")
            return
        ReportGenerator(self.analysis_data).plot_metric('fidelity')

    def _plot_ops(self):
        if not self.analysis_data:
            messagebox.showwarning("No data", "Run analysis first.")
            return
        ReportGenerator(self.analysis_data).plot_ops_breakdown()


if __name__ == "__main__":
    app = QTranspileApp()
    app.mainloop()

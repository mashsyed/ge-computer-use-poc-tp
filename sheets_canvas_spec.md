# Sheets Canvas Specification: Operational Supervisor Dashboard

This specification outlines the architecture, layout, and setup instructions for building a native **Sheets Canvas Dashboard** inside Google Sheets to monitor real-time SLA metrics, status kanbans, and exception triage queues for the Tax Certificate Computer Use Automation system.

---

## 1. Overview & Architecture

Rather than requiring external Business Intelligence tools (such as Looker or Tableau), the operational dashboard is embedded directly into Google Sheets using **Sheets Canvas**. It communicates in real-time with the `Intake_Queue`, `Client_Database`, and `Metrics_Rollup` tabs.

### Key Capabilities
- **Real-Time Operational KPIs**: Live tracking of volume, success rates, queue depth, and execution latency.
- **Status Kanban View**: Visual breakdown of records by processing stage.
- **Exception Triage Queue**: Immediate visibility into failed items needing supervisor intervention with direct access to error logs and screenshot links.
- **Gemini in Sheets Integration**: Built-in AI prompts for automated analysis, trend detection, and layout styling.

---

## 2. Grid & Canvas Layout Architecture

Create a new tab in your Google Spreadsheet named **`Dashboard_Canvas`**.

```
+---------------------------------------------------------------------------------------------------------+
|                                    TAX CERTIFICATE AUTOMATION DASHBOARD                                 |
+---------------------------------------------------------------------------------------------------------+
|  KPI CARD 1             |  KPI CARD 2          |  KPI CARD 3          |  KPI CARD 4         | KPI CARD 5 |
|  Total Processed        |  Success Rate        |  Active Queue        |  Avg Duration       | Exceptions |
|  =Metrics_Rollup!B3     |  =Metrics_Rollup!B5  |  =Metrics_Rollup!B6  |  =Metrics_Rollup!B7 | =Metrics!B8|
+---------------------------------------------------------------------------------------------------------+
|                                                                                                         |
|  SECTION A: STATUS KANBAN SUMMARY                                                                      |
|  +------------------+----------------------+-----------------------+--------------------+               |
|  | READY_FOR_CRM    | IN_CRM_PROCESSING    | COMPLETED             | FAILED_REVIEW      |               |
|  | =COUNTIF(...)    | =COUNTIF(...)        | =COUNTIF(...)         | =COUNTIF(...)      |               |
|  +------------------+----------------------+-----------------------+--------------------+               |
|                                                                                                         |
|  SECTION B: EXCEPTION TRIAGE QUEUE (Action Required)                                                    |
|  +-----------+-----------+------------+------------------+------------------------+------------------+  |
|  | Timestamp | Client ID | Email      | State            | Error Log              | Action Needed    |  |
|  +-----------+-----------+------------+------------------+------------------------+------------------+  |
|  | FILTER(Intake_Queue!A2:I, Intake_Queue!E2:E="FAILED_NEEDS_REVIEW")                               |  |
|  +-----------+-----------+------------+------------------+------------------------+------------------+  |
+---------------------------------------------------------------------------------------------------------+
```

---

## 3. Detailed Component Specifications

### Component A: KPI Metric Cards (Rows 2 - 5)

| Cell / Location | KPI Metric Name | Formula Reference | Formatting |
| :--- | :--- | :--- | :--- |
| **Card 1 (A2:B4)** | **Total Volume** | `=Metrics_Rollup!B3` | Bold Number, Font 22pt, Blue Background |
| **Card 2 (C2:D4)** | **Success Rate (%)** | `=Metrics_Rollup!B5` | Percentage `0.0%`, Green text if > 90% |
| **Card 3 (E2:F4)** | **Active Queue** | `=Metrics_Rollup!B6` | Bold Number, Yellow highlight if > 10 |
| **Card 4 (G2:H4)** | **Avg Duration (Sec)** | `=Metrics_Rollup!B7` | Number `0.0s` |
| **Card 5 (I2:J4)** | **Exceptions / Review** | `=Metrics_Rollup!B8` | Bold Number, Red highlight if > 0 |

---

### Component B: Status Kanban Breakdown (Rows 7 - 12)

Use standard Google Sheets formulas to summarize the active status distribution:

- **Pending / Generating**: `=COUNTIF(Intake_Queue!E:E, "GENERATING_DOC")`
- **Ready for CRM**: `=COUNTIF(Intake_Queue!E:E, "READY_FOR_CRM")`
- **In CRM Processing**: `=COUNTIF(Intake_Queue!E:E, "IN_CRM_PROCESSING")`
- **Completed**: `=COUNTIF(Intake_Queue!E:E, "COMPLETED")`
- **Failed / Review**: `=COUNTIF(Intake_Queue!E:E, "FAILED_NEEDS_REVIEW")`

---

### Component C: Exception Triage Queue View (Rows 14+)

Place a live spill array formula in cell `A15` to automatically pull all failed cases requiring supervisor attention:

```excel
=FILTER(
  CHOOSECOLS(Intake_Queue!A2:J, 1, 2, 3, 4, 8, 9, 10), 
  Intake_Queue!E2:E = "FAILED_NEEDS_REVIEW"
)
```

**Columns Displayed**:
1. Timestamp
2. Client ID
3. Email
4. State
5. Case ID
6. Error Log (Details)
7. Duration (s)

---

## 4. Gemini in Sheets Prompt Templates

When creating or customizing the **Sheets Canvas Dashboard** using Gemini in Sheets (via the side panel or Gemini AI toolbar in Google Workspace), use the following prompt templates:

### Prompt 1: Generate Dashboard Layout & Conditional Formatting
> *"Format the tab `Dashboard_Canvas` as an executive operational dashboard. Create 5 metric highlight cards across row 2 using cell backgrounds #1a73e8, #137333, #f2994a, #17a2b8, and #d93025 with large white text. Add conditional formatting to highlight rows where status is FAILED_NEEDS_REVIEW in soft red (#fce8e6)."*

### Prompt 2: Real-time Exception Alert Summary
> *"Analyze the `Intake_Queue` sheet and create a formula in `Dashboard_Canvas!A15` that extracts all records with status 'FAILED_NEEDS_REVIEW', sorted by timestamp descending, showing Client ID, State, Error Log, and Execution Duration."*

### Prompt 3: Executive SLA Analysis & Bottleneck Identification
> *"Based on the Execution_Duration_Seconds column in `Intake_Queue`, calculate the 90th percentile latency for completed cases and summarize top error categories in `Error_Log`."*

---

## 5. Verification & Testing

1. Run `setupSheetSchemaAndRollups()` in Apps Script (`Code.gs`) to initialize the underlying schema and metrics tab.
2. Verify that values in `Metrics_Rollup` dynamically populate KPI cards on `Dashboard_Canvas`.
3. Submit a test form or manually set a row status to `FAILED_NEEDS_REVIEW` to confirm that the exception row immediately spills into the Triage Queue table.

# Case Study: PipeSafe Analytics — Hazardous Liquid Pipeline Incident Management System

## 1. Organisation / Scenario

**PipeSafe Analytics** is a simulated pipeline safety and compliance organisation that maintains a central incident database for the hazardous liquid pipeline industry. It collects accident reports from pipeline operators, standardises them, and turns them into safety intelligence for operators, investigators and regulators.

The database is populated with **real, publicly available accident data from the U.S. Pipeline and Hazardous Materials Safety Administration (PHMSA)**, covering **6,052** hazardous liquid pipeline accidents reported from **2010 to 2026**. Using real data means the design, queries and performance tests reflect genuine data volumes and quality issues rather than invented examples.

### Data Scope Decision

The source dataset spans 2002–2026, but PHMSA redesigned its hazardous liquid accident report form in 2010. Records from 2002–2009 use the older form, with fewer fields and different field definitions, so the two periods do not share a consistent structure.

This portfolio uses **only the 2010–2026 records** because:

- They follow a single, consistent report format, allowing one clean relational schema
- The post-2010 form is more detailed, with finer cause classification, cost breakdowns and casualties by group
- Over 15 years of records still provide enough volume for query optimisation and performance testing

The pre-2010 records are excluded from the relational design. They may be revisited in Portfolio 4 as an example of how changing record structures can be handled with a flexible NoSQL document model.

## 2. Nature of the Business / System

Pipelines transport crude oil, refined petroleum products (petrol, diesel, jet fuel), highly volatile liquids and CO₂ over long distances. When a pipeline fails, the operator must report the accident to the regulator, including what was released, why it happened, who was harmed, and what it cost.

PipeSafe's system supports this full lifecycle:

- **Recording** each accident reported by an operator
- **Classifying** it by commodity released, cause and pipeline/facility type
- **Measuring** its impact: volume released and recovered, injuries, fatalities and costs
- **Analysing** trends across operators, regions and years to identify recurring risks

## 3. Users of the Database

| User | Role | Main use of the database |
|---|---|---|
| Safety Analysts | PipeSafe staff | Analyse trends, causes and high-risk operators; produce reports |
| Operator Compliance Officers | Staff at pipeline operators | Submit and update accident reports for their own company |
| Incident Investigators | Field/technical investigators | Record cause findings and investigation details |
| Regulators / Auditors | External, read-only | Review accident records and verify reporting compliance |
| Management | PipeSafe leadership | View summary dashboards and key safety indicators |

## 4. Major Data Stored

- **Operators:** the companies that own and run pipelines
- **Pipelines and facilities:** pipeline/facility name, type (onshore/offshore, above/below ground) and system part involved
- **Locations:** state, county, city and geographic coordinates of each accident
- **Accidents:** report number, date and time, and the central record linking everything together
- **Commodities:** the type of liquid released (crude oil, refined products, HVLs, CO₂ and so on)
- **Releases:** volumes unintentionally released, intentionally released and recovered (in barrels)
- **Causes:** cause category and subcategory (e.g., corrosion, equipment failure, excavation damage, incorrect operation)
- **Casualties:** injuries and fatalities, separated by group (operator employees, contractors, emergency responders, general public)
- **Costs:** property damage, lost commodity, emergency response, environmental remediation and other costs

## 5. Key Operations the Database Supports

1. **Log a new accident** with its operator, location, commodity and release details
2. **Update an accident report** as investigation findings and final costs become available
3. **Record cause classification** once the investigation is complete
4. **Search and retrieve** accidents by operator, state, date range, commodity or cause
5. **Calculate impact metrics:** total barrels lost vs recovered, recovery rate, total cost per accident
6. **Generate trend reports:** accidents per year, top causes, most costly incidents, operators with the most accidents
7. **Support compliance audits:** verify that reports are complete and consistent

## 6. Why This Case Study Suits the Portfolio

| Portfolio | How the case study supports it |
|---|---|
| 1. Database Design | The raw PHMSA data is a single wide, flat table with heavy redundancy (repeated operator names, locations and cause labels), making it ideal for demonstrating normalisation to 3NF |
| 2. Query Optimisation | Over 15 years of incident records give enough volume for meaningful execution plans and before/after indexing comparisons |
| 3. Transactions | Logging an accident touches several related tables (accident, release, casualties, costs) that must succeed or fail together |
| 4. NoSQL | Accident reports vary in structure by commodity and cause, and the report format itself changed in 2010, both of which suit a flexible document model |
| 5. Distributed / Cloud | Reports come from operators across many states, supporting a discussion of regional sharding, replication and availability |

## 7. Data Source

- U.S. Department of Transportation, Pipeline and Hazardous Materials Safety Administration (PHMSA). *Hazardous Liquid Accident Data, January 2010 to present.* Downloaded 26 October 2026 from https://www.phmsa.dot.gov/data-and-statistics/pipeline/distribution-transmission-gathering-lng-and-liquid-accident-and-incident-data
- Kaggle upload: Oscarpez, *U.S. Hazardous Liquid Pipeline Accidents 2002–2026*. https://www.kaggle.com/datasets/oscarpez/u-s-hazardous-liquid-pipeline-accidents-20022026

> **Note:** PipeSafe Analytics is a simulated organisation created for this portfolio. The accident data is real and publicly available; all organisational details (name, users, workflows) are illustrative.

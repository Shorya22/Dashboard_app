# Workforce Analytics Platform -- Data Ingestion, Versioning & Historical Data Management

## Vision

Transform the current Excel-based dashboard into an enterprise Workforce
Analytics Platform where:

-   Excel is only an ingestion source.
-   The dashboard never reads Excel directly.
-   Every upload is validated before import.
-   Historical data is immutable.
-   Every change is auditable.
-   Future features (RBAC, Row-Level Security, AI, multiple business
    modules) can be added without redesigning the platform.

------------------------------------------------------------------------

# Current Challenges

Current flow:

``` text
User
   │
Upload Excel
   │
Backend reads Excel directly
   │
Dashboard
```

Problems:

-   Data is overwritten.
-   No historical reporting.
-   No audit trail.
-   Difficult to implement RBAC.
-   Difficult to scale.
-   Difficult to build trust.

------------------------------------------------------------------------

# Target Architecture

``` text
                 Admin Portal
                      │
              Upload Excel Files
                      │
                      ▼
            File Registration Service
                      │
                      ▼
             Validation Engine
                      │
         ┌────────────┴────────────┐
         │                         │
 Validation Failed          Validation Passed
         │                         │
 Validation Report               ▼
                          Transformation Engine
                                  │
                                  ▼
                           Snapshot Creation
                                  │
                                  ▼
                            Import Engine
                                  │
                                  ▼
                        PostgreSQL / Azure SQL
                                  │
                                  ▼
                           Dashboard APIs
                                  │
                                  ▼
                           React Dashboard
```

------------------------------------------------------------------------

# Implementation Roadmap

## Phase 1 -- Excel Upload Module

### Objective

Treat Excel as an import source rather than the application's database.

### Features

-   Upload dataset
-   Dataset type
-   Reporting period
-   Optional comments
-   File version

Supported datasets:

-   Employee Roster
-   Bookings
-   Ground Truth
-   Finance
-   Recruitment
-   Operations

------------------------------------------------------------------------

## Phase 2 -- Upload Registration

Create an upload record before processing.

### Upload Table

  Column         Description
  -------------- -------------------
  upload_id      Unique ID
  dataset_type   Dataset
  period         Reporting period
  file_name      Uploaded file
  uploaded_by    User
  uploaded_at    Timestamp
  status         Processing status
  file_hash      SHA-256
  remarks        Comments

Statuses:

-   Uploading
-   Validating
-   Validation Failed
-   Ready for Import
-   Imported
-   Archived

------------------------------------------------------------------------

## Phase 3 -- Validation Engine

Pipeline

``` text
Upload
   │
Security Validation
   │
Workbook Validation
   │
Schema Validation
   │
Business Validation
   │
Cross Dataset Validation
   │
Validation Report
```

### Security Validation

-   File extension
-   Password protection
-   Macros
-   Duplicate upload
-   Corrupted workbook

### Schema Validation

-   Required columns
-   Data types
-   Missing columns
-   Duplicate columns
-   Date formats

### Business Validation

-   Employee ID unique
-   Hours \<= 24
-   Valid Market
-   Valid Entity
-   Valid Department

### Cross Dataset Validation

-   Booking employee exists in roster
-   Project exists
-   Entity exists

Return every error in one report.

------------------------------------------------------------------------

## Phase 4 -- Data Transformation

Standardise uploaded data.

Examples:

-   Trim spaces
-   Uppercase values
-   Standardise entity names
-   Convert dates
-   Map column names

------------------------------------------------------------------------

## Phase 5 -- Snapshot & Versioning

Never overwrite data.

Instead of replacing July data:

``` text
July V1

↓

July V2

↓

July V3
```

Snapshots table:

  snapshot_id   period   version   status
  ------------- -------- --------- ----------
  101           July     V1        Archived
  102           July     V2        Archived
  103           July     V3        Active

Benefits:

-   No overwritten data
-   Historical reporting
-   Rollback
-   Trustworthy reports

------------------------------------------------------------------------

## Phase 6 -- Import Engine

Import validated data into relational tables.

Every business table includes:

-   snapshot_id

Examples:

Employees

-   employee_id
-   snapshot_id
-   market
-   entity

Bookings

-   booking_id
-   snapshot_id
-   employee_id
-   hours

------------------------------------------------------------------------

## Phase 7 -- Atomic Transactions

``` text
Begin Transaction
      │
Import Employees
      │
Import Bookings
      │
Commit
```

Failure:

``` text
Rollback Everything
```

No partial imports.

------------------------------------------------------------------------

## Phase 8 -- Snapshot Lifecycle

``` text
Upload
   │
Draft
   │
Validation Passed
   │
Pending Approval
   │
Approved
   │
Active
   │
Archived
```

------------------------------------------------------------------------

## Phase 9 -- Audit Trail

Record every action.

Audit table:

-   audit_id
-   user
-   action
-   dataset
-   snapshot
-   timestamp
-   remarks

Examples:

-   Upload
-   Validation
-   Approval
-   Activation
-   Rollback

------------------------------------------------------------------------

## Phase 10 -- Dashboard Data Service

``` text
Dashboard
   │
REST API
   │
Database
   │
Latest Active Snapshot
   │
Charts
```

------------------------------------------------------------------------

# Historical Data Strategy

The dashboard always displays an approved snapshot.

Older snapshots remain unchanged.

Advantages:

-   Immutable history
-   Version comparison
-   Rollback
-   Accurate historical reporting
-   Full auditability

------------------------------------------------------------------------

# Future Enhancements

-   RBAC
-   Row-Level Security
-   Admin Portal
-   Multi-module support
-   AI Chatbot
-   Notifications

------------------------------------------------------------------------

# Suggested Technology Stack

  Layer        Technology
  ------------ ----------------------------------
  Frontend     React + Vite
  Backend      FastAPI
  Excel        Pandas + OpenPyXL
  Validation   Pandera
  ORM          SQLAlchemy
  Database     PostgreSQL / Azure SQL
  Migrations   Alembic
  Storage      Azure Blob Storage
  Jobs         FastAPI BackgroundTasks / Celery

------------------------------------------------------------------------

# Master Prompt for AI Development

## System Goal

Build an enterprise-grade Excel ingestion platform for a Workforce
Analytics application.

### Requirements

1.  Excel must be treated as an ingestion source only.
2.  Dashboard must never read Excel directly.
3.  Validate uploaded files using:
    -   Security validation
    -   Schema validation
    -   Business validation
4.  Return all validation errors in one report.
5.  Transform uploaded data into a canonical model.
6.  Import data into PostgreSQL using transactions.
7.  Every import must create an immutable snapshot.
8.  Never overwrite historical data.
9.  Support rollback by changing the active snapshot.
10. Maintain complete audit logs.
11. Design with SOLID principles.
12. Use FastAPI, SQLAlchemy 2.x, Alembic, Pandera, Pandas and
    PostgreSQL.
13. Produce clean, modular, production-ready code with tests and API
    documentation.
14. Keep the design extensible for future RBAC, Row-Level Security,
    Admin Portal and AI features.

### Expected Deliverables

-   Database schema
-   Folder structure
-   API design
-   Import pipeline
-   Validation framework
-   Snapshot/version management
-   Audit logging
-   Rollback strategy
-   Sequence diagrams
-   Error handling
-   Unit and integration tests

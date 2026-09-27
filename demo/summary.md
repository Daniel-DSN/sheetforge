# SheetForge clean report

Input: `samples/messy.csv`

| Metric | Value |
|--------|-------|
| Rows in | 30 |
| Rows out | 25 |
| Exact duplicates removed | 3 |
| email duplicates removed | 2 |
| Emails valid | 19 |
| Emails invalid | 6 |
| Phones fixed | 12 |
| Phones invalid | 1 |
| Columns coerced to number | order_value |
| Flagged rows | 7 |

## Flagged rows

| row | reason |
|-----|--------|
| 6 | invalid email: fabio@@x |
| 9 | invalid email: igor@ |
| 14 | invalid email: lucas.ferreira@ |
| 19 | invalid phone: 99999-0017 |
| 22 | invalid email: bad email.com |
| 26 | invalid email: vitor.barros@ |
| 30 | invalid email: zeca.camargo@@y |

cols = ["ptype","course_id","job_title","department","campus","posting_date","closing_date"]
display_names = ["Type","Course","Title","Department","Campus","Posted","Closes"]
dropdown_not_search = [1,0,0,0,1,1,1]


import pandas as pd
# Read the CSV file into a pandas DataFrame
df = pd.read_csv("result.csv")
print(sorted(df.columns))


def strip_whitespace(x):
    if isinstance(x, str):
        return x.strip()
    else:
        return x
df = df.map(strip_whitespace)


def format_date_column(frame, column_name):
    parsed = pd.to_datetime(frame[column_name], errors='coerce')
    formatted = parsed.dt.strftime('%Y.%m.%d')
    frame[column_name] = formatted.where(parsed.notna(), frame[column_name])


format_date_column(df, "posting_date")
format_date_column(df, "closing_date")


#course_id_to_id = dict(zip(df['course_id'], df['id']))
df["course_id"]+="|"+df["id"].astype(str)
df = df[cols]

# Rename columns to human-readable display names
df.columns = display_names

# Convert the DataFrame to an HTML table
html_table = df.to_html(index=False,header=True)
footer = "<tfoot>\n<tr>" + " ".join(["<th>"+ i +"</th>\n" for i in df.columns])+"</tr>\n  </tfoot>"


indices_of_search = [index for index, value in enumerate(dropdown_not_search) if value == 0]
indices_of_dropdown = [index for index, value in enumerate(dropdown_not_search) if value == 1]


html_table = html_table.replace(
    """<table border="1" class="dataframe">""",
    """<table id="jobs" border=0 style="width:100%" class="display compact">"""
)
html_table = html_table.replace(
    "<thead>",
    footer+"<thead>"
)


htmlstr = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CUPE 3902 Unit 1 Job Postings — UofT</title>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">
    <script src="https://code.jquery.com/jquery-3.6.4.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
    <style>
        * { box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 12px 20px;
            background: #fafafa;
            color: #222;
            font-size: 14px;
        }

        h1 {
            font-size: 18px;
            font-weight: 600;
            margin: 0 0 2px 0;
            color: #1a1a2e;
        }
        .subtitle {
            font-size: 12px;
            color: #666;
            margin: 0 0 12px 0;
        }

        /* Toolbar: toggle + dataTables controls on one line */
        .toolbar {
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }
        .toolbar label {
            font-size: 12px;
            color: #444;
            cursor: pointer;
            user-select: none;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .toolbar input[type="checkbox"] {
            accent-color: #1a5276;
            margin: 0;
        }

        /* DataTables overrides */
        table.dataTable {
            border-collapse: collapse !important;
            width: 100% !important;
        }
        table.dataTable thead th {
            background: #1a1a2e;
            color: #fff;
            font-weight: 600;
            font-size: 12px;
            padding: 7px 8px;
            border-bottom: none;
            text-align: left;
        }
        table.dataTable thead th.sorting:after,
        table.dataTable thead th.sorting_asc:after,
        table.dataTable thead th.sorting_desc:after {
            opacity: 0.7;
        }
        /* Filter row (tfoot shown above tbody) */
        tfoot {
            display: table-header-group;
        }
        table.dataTable tfoot th {
            background: #f0f0f0;
            padding: 4px 4px;
            border-bottom: 1px solid #ddd;
            font-weight: normal;
        }
        table.dataTable tfoot input,
        table.dataTable tfoot select {
            width: 100%;
            padding: 4px 5px 4px 24px;
            font-size: 12px;
            border: 1px solid #bbb;
            border-radius: 3px;
            background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23999' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cline x1='21' y1='21' x2='16.65' y2='16.65'/%3E%3C/svg%3E") 6px center no-repeat;
            color: #333;
        }
        table.dataTable tfoot select {
            padding-left: 5px;
            background-image: none;
        }
        table.dataTable tfoot input:focus,
        table.dataTable tfoot select:focus {
            outline: none;
            border-color: #1a5276;
            box-shadow: 0 0 0 1px #1a527633;
        }

        /* Body rows */
        table.dataTable tbody td {
            padding: 5px 8px;
            border-bottom: 1px solid #e8e8e8;
            vertical-align: top;
            font-size: 14px;
        }
        table.dataTable tbody tr:hover td {
            background: #e8f0fe !important;
        }
        table.dataTable.stripe tbody tr.odd td,
        table.dataTable tbody tr.odd td {
            background: #fff;
        }
        table.dataTable.stripe tbody tr.even td,
        table.dataTable tbody tr.even td {
            background: #edf0f5;
        }
        /* Expired rows get dimmed */
        table.dataTable tbody tr.expired td {
            color: #999;
        }
        table.dataTable tbody tr.expired a {
            color: #8aa;
        }

        /* Type column: compact badge */
        .badge {
            display: inline-block;
            padding: 1px 6px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.3px;
        }
        .badge-ta { background: #d4edda; color: #155724; }
        .badge-ci { background: #cce5ff; color: #004085; }

        /* DataTables info/pagination area */
        .dataTables_wrapper .dataTables_length,
        .dataTables_wrapper .dataTables_filter,
        .dataTables_wrapper .dataTables_info,
        .dataTables_wrapper .dataTables_paginate {
            font-size: 12px;
            color: #555;
        }
        .dataTables_wrapper .dataTables_filter {
            display: none; /* we have per-column filters, the global search box is redundant */
        }
        .dataTables_wrapper .dataTables_length select {
            padding: 2px 4px;
            border: 1px solid #ccc;
            border-radius: 3px;
        }
        .dataTables_wrapper .dataTables_paginate .paginate_button.current,
        .dataTables_wrapper .dataTables_paginate .paginate_button.current:hover {
            background: #1a1a2e !important;
            color: #fff !important;
            border: 1px solid #1a1a2e;
            border-radius: 3px;
        }
        .dataTables_wrapper .dataTables_paginate .paginate_button:hover {
            background: #e8f0fe !important;
            border-color: #ccc;
            border-radius: 3px;
            color: #222 !important;
        }

        /* Column widths */
        table.dataTable th:nth-child(1),
        table.dataTable td:nth-child(1) { width: 44px; }
        table.dataTable th:nth-child(6),
        table.dataTable td:nth-child(6),
        table.dataTable th:nth-child(7),
        table.dataTable td:nth-child(7) { width: 80px; white-space: nowrap; }
    </style>
</head>
<body>

    <h1>CUPE 3902 Unit 1 — Job Postings</h1>
    <p class="subtitle">University of Toronto · TA &amp; CI positions</p>

    <div class="toolbar">
        <label for="showExpiredToggle">
            <input type="checkbox" id="showExpiredToggle">
            <span id="showExpiredLabel">Show expired postings</span>
        </label>
    </div>

    $$html_table$$


<script>
$(document).ready(function () {
    var STORE_KEY = 'cupe3902_filters';
    var CLOSES_COL = 6;

    // --- localStorage helpers ---
    function loadState() {
        try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch(e) { return {}; }
    }
    function saveState(patch) {
        var s = loadState();
        for (var k in patch) s[k] = patch[k];
        localStorage.setItem(STORE_KEY, JSON.stringify(s));
    }

    var saved = loadState();
    var showExpiredJobs = !!saved.expired;
    $('#showExpiredToggle').prop('checked', showExpiredJobs);

    function parseDateString(dateStr) {
        if (!dateStr || dateStr.length !== 10) return null;
        var parts = dateStr.split('.');
        if (parts.length !== 3) return null;
        var y = parseInt(parts[0], 10), m = parseInt(parts[1], 10) - 1, d = parseInt(parts[2], 10);
        if (isNaN(y) || isNaN(m) || isNaN(d)) return null;
        return new Date(y, m, d);
    }

    function isExpired(dateStr) {
        var cd = parseDateString(dateStr);
        if (!cd) return false;
        var today = new Date(); today.setHours(0,0,0,0);
        return cd < today;
    }

    // Custom filter: hide expired unless toggled
    $.fn.dataTable.ext.search.push(function (settings, data) {
        if (settings.nTable.id !== 'jobs') return true;
        if (showExpiredJobs) return true;
        var cd = parseDateString(data[CLOSES_COL]);
        if (!cd) return true;
        var today = new Date(); today.setHours(0,0,0,0);
        return cd >= today;
    });

    var table = $('#jobs').DataTable({
        columnDefs: [
            // Course column: render as link
            {
                targets: 1,
                render: function (data, type) {
                    if (type === 'display') {
                        var i = data.lastIndexOf('|');
                        var num_id = data.substring(i + 1);
                        var course = data.substring(0, i);
                        return '<a href="https://unit1.hrandequity.utoronto.ca/posting/' + num_id + '">' + course + '</a>';
                    }
                    return data;
                }
            },
            // Type column: render as badge
            {
                targets: 0,
                render: function (data, type) {
                    if (type === 'display') {
                        var cls = data === 'TA' ? 'badge-ta' : data === 'CI' ? 'badge-ci' : '';
                        return '<span class="badge ' + cls + '">' + data + '</span>';
                    }
                    return data;
                }
            }
        ],
        autoWidth: false,
        order: [[6, 'asc']], // default sort by closing date
        lengthMenu: [[-1, 25, 50], ['All', 25, 50]],
        pageLength: -1,
        dom: 'lrtip', // length, processing, table, info, pagination (no global filter)
        language: {
            lengthMenu: 'Show _MENU_ entries',
            info: '_TOTAL_ postings',
            infoFiltered: '(filtered from _MAX_)',
            infoEmpty: 'No postings',
            emptyTable: 'No matching postings found'
        },
        createdRow: function (row, data) {
            if (isExpired(data[CLOSES_COL])) {
                $(row).addClass('expired');
            }
        },
        initComplete: function () {
            var api = this.api();
            var savedCols = saved.cols || {};

            // Search inputs for text-search columns
            api.columns($$indices_of_search$$)
                .every(function () {
                    var column = this;
                    var idx = column.index();
                    var title = $(column.header()).text();
                    var input = document.createElement('input');
                    input.setAttribute('type', 'text');
                    input.setAttribute('placeholder', title + '...');
                    column.footer().replaceChildren(input);

                    // Restore saved value
                    if (savedCols[idx]) {
                        input.value = savedCols[idx];
                        column.search(savedCols[idx]);
                    }

                    input.addEventListener('keyup', function () {
                        column.search(this.value).draw();
                        var patch = {}; patch[idx] = this.value;
                        saveState({ cols: Object.assign(savedCols, patch) });
                    });
                });

            // Dropdowns for categorical columns
            api.columns($$indices_of_dropdown$$)
                .every(function () {
                    var column = this;
                    var idx = column.index();
                    var title = $(column.header()).text();
                    var select = document.createElement('select');
                    select.add(new Option('All ' + title, ''));
                    column.footer().replaceChildren(select);
                    column.data().unique().sort().each(function (d) {
                        select.add(new Option(d));
                    });

                    // Restore saved value
                    if (savedCols[idx]) {
                        select.value = savedCols[idx];
                        var val = $.fn.dataTable.util.escapeRegex(savedCols[idx]);
                        column.search(val ? '^' + val + '$' : '', true, false);
                    }

                    select.addEventListener('change', function () {
                        var val = $.fn.dataTable.util.escapeRegex(select.value);
                        column.search(val ? '^' + val + '$' : '', true, false).draw();
                        var patch = {}; patch[idx] = select.value;
                        saveState({ cols: Object.assign(savedCols, patch) });
                    });
                });

            // Draw once after restoring all filters
            api.draw();
        },
    });

    $('#showExpiredToggle').on('change', function () {
        showExpiredJobs = this.checked;
        saveState({ expired: showExpiredJobs });
        table.draw();
    });
});
</script>
</body>
</html>
"""


replacements ="""
html_table
indices_of_search
indices_of_dropdown
""".strip().split()
string_of_variable = []
for varStr in replacements:
    varName = f'$${varStr}$$'
    var = eval(varStr)
    htmlstr = htmlstr.replace(varName,str(var))


with open("index.html", mode='w') as f:
    f.write(htmlstr)





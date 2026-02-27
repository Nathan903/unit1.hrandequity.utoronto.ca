cols = ["ptype","course_id","job_title","department","campus","posting_date","closing_date"]
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


# Convert the DataFrame to an HTML table
html_table = df.to_html(index=False,header=True)
footer = "<tfoot>\n" + " ".join(["<th>"+ i +"</th>\n" for i in df.columns])+"</tr>\n  </tfoot>"


indices_of_search = [index for index, value in enumerate(dropdown_not_search) if value == 0]
indices_of_dropdown = [index for index, value in enumerate(dropdown_not_search) if value == 1]


html_table = html_table.replace(
    """<table border="1" class="dataframe">""",
    """<table id="example" border=0 style="width:100%" class="display">"""
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
    <title>UofT CUPE Local 3902 Unit 1 Job Postings</title>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.10.24/css/jquery.dataTables.min.css">
    <script src="https://code.jquery.com/jquery-3.6.4.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
    <style type="text/css">
        tfoot {
            display: table-header-group;
        }

        .expired-toggle-container {
            display: flex;
            align-items: center;
            gap: 12px;
            margin: 16px 0;
            font-family: Arial, sans-serif;
        }

        .switch {
            position: relative;
            display: inline-block;
            width: 48px;
            height: 26px;
        }

        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #bdbdbd;
            transition: .2s;
            border-radius: 26px;
        }

        .slider:before {
            position: absolute;
            content: "";
            height: 20px;
            width: 20px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .2s;
            border-radius: 50%;
        }

        .switch input:checked + .slider {
            background-color: #1f77b4;
        }

        .switch input:checked + .slider:before {
            transform: translateX(22px);
        }

        .expired-toggle-label {
            font-size: 14px;
            color: #333;
            cursor: pointer;
        }
    </style>
</head>
<body>

    <div class="expired-toggle-container">
        <label class="switch" for="showExpiredToggle">
            <input type="checkbox" id="showExpiredToggle">
            <span class="slider"></span>
        </label>
        <label class="expired-toggle-label" for="showExpiredToggle" id="showExpiredLabel">Showing active jobs only</label>
    </div>


    $$html_table$$


<script>
$(document).ready(function () {
    var showExpiredJobs = false;

    function parseDateString(dateStr) {
        if (!dateStr || dateStr.length !== 10) {
            return null;
        }

        var parts = dateStr.split('.');
        if (parts.length !== 3) {
            return null;
        }

        var year = parseInt(parts[0], 10);
        var month = parseInt(parts[1], 10) - 1;
        var day = parseInt(parts[2], 10);

        if (isNaN(year) || isNaN(month) || isNaN(day)) {
            return null;
        }

        return new Date(year, month, day);
    }

    $.fn.dataTable.ext.search.push(function (settings, data) {
        if (settings.nTable.id !== 'example') {
            return true;
        }

        if (showExpiredJobs) {
            return true;
        }

        var closingDate = parseDateString(data[6]);
        if (!closingDate) {
            return true;
        }

        var today = new Date();
        today.setHours(0, 0, 0, 0);

        return closingDate >= today;
    });

    // Setup - add a text input to each footer cell
    $('#example tfoot th').each(function () {
        var title = $('#example thead th').eq($(this).index()).text();
        $(this).html('<input type="text" placeholder="Search ' + title + '" />');
    });


    // DataTable
    var table = $('#example').DataTable({


        columnDefs: [
          {
            targets: 1,
                render: function (data, type, row, meta) {
                    if (type === 'display') {
                        let lastIndex = data.lastIndexOf("|");  
                        let num_id = data.substring(lastIndex + 1);
                        let course_id = data.substring(0, lastIndex);
                        return "<a href=\"https://unit1.hrandequity.utoronto.ca/posting/"+num_id+"\">"+course_id+"</a>"; //'<a href="https://unit1.hrandequity.utoronto.ca/posting/</a>';
                       
                    }
                    return data;
                }
            }
        ],
        autoWidth: false,


        lengthMenu: [
            [-1, 10, 25, 50],
            ['All', 10, 25, 50]
        ],
        initComplete: function () {
            // Separate logic for the first two
           
            this.api()
                .columns($$indices_of_search$$)
                .every(function () {
                    let column = this;
                    var title = $(column.header()).text();


                    // Create input element
                    let input = document.createElement('input');
                    input.setAttribute('type', 'text');
                    column.footer().replaceChildren(input);
                    input.setAttribute('placeholder', 'Search ' + title); // Set the placeholder attribute


                    // Apply listener for user change in value
                    input.addEventListener('keyup', function () {
                        column
                            .search(this.value)
                            .draw();
                    });
                });


            // Separate logic for the remaining four columns
            this.api()
                .columns($$indices_of_dropdown$$)
                .every(function () {
                    let column = this;


                    // Create select element
                    let select = document.createElement('select');
                    select.add(new Option(''));
                    column.footer().replaceChildren(select);


                    // Apply listener for user change in value
                    select.addEventListener('change', function () {
                        var val = $.fn.dataTable.util.escapeRegex(select.value);


                        column
                            .search(val ? '^' + val + '$' : '', true, false)
                            .draw();
                    });


                    // Add list of options
                    column
                        .data()
                        .unique()
                        .sort()
                        .each(function (d, j) {
                            select.add(new Option(d));
                        });
                });
        },
    });

    $('#showExpiredToggle').on('change', function () {
        showExpiredJobs = this.checked;
        $('#showExpiredLabel').text(
            showExpiredJobs
                ? 'Showing all jobs (including expired)'
                : 'Showing active jobs only'
        );
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





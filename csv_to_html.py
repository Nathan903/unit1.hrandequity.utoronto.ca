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
df = df.applymap(strip_whitespace)

course_id_to_id = dict(zip(df['course_id'], df['id']))

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
    </style>
</head>
<body>

    $$html_table$$

<script>
const course_id_to_id = $$course_id_to_id$$;
$(document).ready(function () {
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
                        //course_id_to_id[data] APS112
                        if(data in course_id_to_id){
                        return "<a href=\"https://unit1.hrandequity.utoronto.ca/posting/"+course_id_to_id[data]+"\">"+data+"</a>"; //'<a href="https://unit1.hrandequity.utoronto.ca/posting/</a>';
                        }
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

});
</script>
</body>
</html>

"""

replacements ="""
html_table
indices_of_search
indices_of_dropdown
course_id_to_id
""".strip().split()
string_of_variable = []
for varStr in replacements:
    varName = f'$${varStr}$$'
    var = eval(varStr)
    htmlstr = htmlstr.replace(varName,str(var))

with open("index.html", mode='w') as f:
    f.write(htmlstr)

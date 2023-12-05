import pandas as pd

# Read the CSV file into a pandas DataFrame
df = pd.read_csv("result.csv")
print(sorted(df.columns))
cols = ["course_id","job_title","department","campus","posting_date","closing_date"]

df = df[cols]
# Convert the DataFrame to an HTML table
html_table = df.to_html(index=False,header=True)
footer = "<tfoot>\n" + " ".join(["<th>"+ i +"</th>\n" for i in df.columns])+"</tr>\n  </tfoot>"


html_table = html_table.replace(
    """<table border="1" class="dataframe">""",
    """<table id="example" border="1" style="width:100%" class="display">"""
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
    <title>DataTables Column Search Example</title>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.10.24/css/jquery.dataTables.min.css">
    <script src="https://code.jquery.com/jquery-3.6.4.min.js"></script>
    <script src="https://cdn.datatables.net/1.10.24/js/jquery.dataTables.min.js"></script>
    <style type="text/css">
        tfoot {
            display: table-header-group;
        }
    </style>
</head>
<body>

    $$table$$

<script>
$(document).ready(function () {
    // Setup - add a text input to each footer cell
    $('#example tfoot th').each(function () {
        var title = $('#example thead th').eq($(this).index()).text();
        $(this).html('<input type="text" placeholder="Search ' + title + '" />');
    });

    // DataTable
    var table = $('#example').DataTable({
        lengthMenu: [
            [-1, 10, 25, 50],
            ['All', 10, 25, 50]
        ],

        initComplete: function () {
            // Separate logic for the first two columns
            this.api()
                .columns([0, 1,2])
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
                .columns([3, 4, 5])
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

""".replace("$$table$$",html_table)
with open("index.html", mode='w') as f:
    f.write(htmlstr)

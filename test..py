import pandas as pd

# Read the CSV file into a pandas DataFrame
df = pd.read_csv("result.csv")
print(sorted(df.columns))
cols = ["course_id","job_title","department","campus","posting_date","closing_date"]

df = df[cols]
# Convert the DataFrame to an HTML table
html_table = df.to_html(index=False)

html_table = html_table.replace(
    """<table border="1" class="dataframe">""",
    """<table id="example" border="1" style="width:100%" class="display">"""
)

htmlstr = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DataTables Example</title>

    <!-- Include jQuery -->
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>

    <!-- Include DataTables CSS and JS -->
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">
    <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
    <style>

    tfoot input {
        width: 100%;
        padding: 3px;
        box-sizing: border-box;
    }
    </style>
</head>
<body>

    <h2>DataTable Example</h2>

    $$table$$
    <script>


new DataTable('#example', {
    initComplete: function () {
        this.api()
            .columns()
            .every(function () {
                let column = this;
                let title = column.footer().textContent;
 
                // Create input element
                let input = document.createElement('input');
                input.placeholder = title;
                column.footer().replaceChildren(input);
 
                // Event listener for user input
                input.addEventListener('keyup', () => {
                    if (column.search() !== this.value) {
                        column.search(input.value).draw();
                    }
                });
            });
    }
});
    </script>

</body>
</html>
""".replace("$$table$$",html_table)
with open("result.html", mode='w') as f:
    f.write(htmlstr)

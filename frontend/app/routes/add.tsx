
import type { ActionFunctionArgs, MetaFunction } from "@remix-run/node";
import { Form, useLoaderData } from "@remix-run/react";
import ProjectType from "~/types/project";
import { redirect } from "@remix-run/node";


export async function action({
    request,
}: ActionFunctionArgs) {
    const body = await request.formData();


    console.log(body);
    const name = body.get("name");

    if (!name) {
        return null;
    }

    const directory_name = name.replace(/\s+/g, '-').toLowerCase();


    const project: ProjectType = await fetch(`http://localhost:5000/api/projects/${directory_name}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name }),
    }).then(res => res.json());

    return redirect(`/project/${project.directory_name}`);
}



export default function Index() {




    return <div>
        <Form method="post">
            <input name="name" type="text" />

            <button type="submit">Submit</button>
        </Form>
    </div>
}